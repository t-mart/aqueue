from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial

import trio

from aqueue.display import WAIT_MESSAGE, Display, LinkedTask
from aqueue.queue import QUEUE_FACTORY, Item, ItemNode, Queue, QueueTypeName


async def _worker(
    queue: Queue,
    display: Display,
    worker_status_task: LinkedTask,
    update_queue_size_progress: Callable[..., None],
    graceful_ctrl_c: bool,
):
    async for item_node in queue:

        def enqueue(*children: Item) -> None:
            for child in children:
                child_item_node = ItemNode(item=child, parent=item_node)
                queue.put(child_item_node)
                item_node.children.add(child_item_node)
                if child.track_overall:
                    display.overall_task.total_f += 1

        def set_worker_desc(description: str) -> None:
            worker_status_task.description = description

        with trio.CancelScope(shield=graceful_ctrl_c):
            await item_node.item.process(enqueue, set_worker_desc)
            item_node.done_processing = True

            cur_node: ItemNode | None = item_node
            while cur_node:
                if cur_node.tree_done:
                    await cur_node.item.after_children_processed()
                cur_node = cur_node.parent

        if item_node.item.track_overall:
            display.overall_task.completed += 1
        worker_status_task.description = WAIT_MESSAGE
        update_queue_size_progress()
        queue.task_done()

    worker_status_task.description = "Done"


async def async_run_queue(
    *,
    initial_items: Iterable[Item],
    num_workers: int = 5,
    queue_type_name: QueueTypeName,
    graceful_ctrl_c: bool = True,
) -> None:
    """
    An asynchronous version of `run_queue`. This method must be run in a Trio event
    loop.
    """
    queue = QUEUE_FACTORY[queue_type_name]()

    display = Display.create()
    update_queue_size_progress = display.create_update_queue_size_progress_fn(queue)

    display.live.start()

    async with trio.open_nursery() as nursery:
        for item in initial_items or []:
            queue.put(ItemNode(item=item, parent=None))
            if item.track_overall:
                display.overall_task.total_f += 1

        for worker_id in range(num_workers):
            worker_status_task = display.create_worker_status_task(worker_id=worker_id)

            nursery.start_soon(
                partial(
                    _worker,
                    queue=queue,
                    display=display,
                    worker_status_task=worker_status_task,
                    update_queue_size_progress=update_queue_size_progress,
                    graceful_ctrl_c=graceful_ctrl_c,
                ),
                name=f"worker #{worker_id}",  # for debugging/introspection
            )

    display.live.stop()


def run_queue(
    *,
    initial_items: Iterable[Item],
    num_workers: int = 5,
    queue_type_name: QueueTypeName = "queue",
    graceful_ctrl_c: bool = True,
) -> None:
    """
    Process all items in initial items (and any subsequent items they produce) and
    display a terminal visualization of it.

    - `initial_items` is an iterable that seeds the queue. This is where the top-level
      item should go that produces more items. (Note that any subsequent item can also
      produce items.)
    - `num_workers` specifies how many workers will be running concurrently. Defaults
      to 5.
    - `queue_type_name` can be either of:
      - `queue` for first-in-first-out processing, the default
      - `stack` for last-in-first-out processing
      - `priority` for priority-based processing. In this case, item objects should be
        orderable. Processing will occur in *ascending* priority (smallest first).
    - `graceful_ctrl_c` specifies whether pressing Ctrl-C will stop things abruptly
      (False) or wait until all the currently worked-on items are finished first (True,
      the default).
    """

    trio.run(
        partial(
            async_run_queue,
            queue_type_name=queue_type_name,
            initial_items=initial_items,
            num_workers=num_workers,
            graceful_ctrl_c=graceful_ctrl_c,
        ),
        restrict_keyboard_interrupt_to_checkpoints=False,
    )
