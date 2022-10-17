from __future__ import annotations

from collections.abc import Iterable
from functools import partial

import trio

from aqueue.display import WAIT_MESSAGE, Display, LinkedTask
from aqueue.queue import QUEUE_FACTORY, Item, Queue, Ordering


async def _worker(
    queue: Queue,
    display: Display,
    worker_status_task: LinkedTask,
    graceful_ctrl_c: bool,
):
    async for item in queue:
        display.remove_from_queue(item)

        def enqueue(*children: Item) -> None:
            for child in children:
                child.parent = item
                queue.put(child)
                display.add_to_queue(child)
                item._children.append(child)
                if child.track_overall:
                    display.overall_task.total_f += 1

        def set_worker_desc(description: str) -> None:
            worker_status_task.description = description

        with trio.CancelScope(shield=graceful_ctrl_c):
            await item._process(enqueue, set_worker_desc)

            cur_item: Item | None = item
            while cur_item:
                if not cur_item._tree_done:
                    break
                await cur_item.after_children_processed()
                cur_item = cur_item.parent

        if item.track_overall:
            display.overall_task.completed += 1
        worker_status_task.description = WAIT_MESSAGE
        queue.task_done()

    worker_status_task.description = "Done"


async def async_run_queue(
    *,
    initial_items: Iterable[Item],
    num_workers: int = 5,
    order: Ordering,
    graceful_ctrl_c: bool = True,
) -> None:
    """
    An asynchronous version of `aqueue.run_queue`. This method must be run in a Trio
    event loop.
    """
    queue = QUEUE_FACTORY[order]()

    display = Display.create(queue=queue)

    display.live.start()

    async with trio.open_nursery() as nursery:
        for item in initial_items or []:
            queue.put(item)
            display.add_to_queue(item)
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
                    graceful_ctrl_c=graceful_ctrl_c,
                ),
                name=f"worker #{worker_id}",  # for debugging/introspection
            )

    display.live.stop()


def run_queue(
    *,
    initial_items: Iterable[Item],
    num_workers: int = 5,
    order: Ordering = "lifo",
    graceful_ctrl_c: bool = True,
) -> None:
    """
    Process all items in ``initial_items`` (and any subsequent items they enqueue) until
    they are complete. Meanwhile, display a terminal visualization of it.

    :param Iterable[Item] initial_items: An iterable that seeds the queue. This is where
        the top-level item(s) should go that produces more items.

    :param int num_workers: Specifies how many workers will be running concurrently.

        .. note::

           Setting a high ``num_workers`` does not automatically mean your program will
           run faster.

    :param Literal["lifo", "fifo", "priority"] order: Can be either of:

        - ``lifo`` for last-in-first-out processing, or depth-first. This one is
          recommended for website scraping because it yields items fast (versus
          ``queue`` that processes intermediate Items first).

        - ``fifo`` for first-in-first-out processing, or breadth-first. This is the
          default.

        - ``priority`` for priority-based processing. In this case, processing will
          occur by *ascending* `aqueue.Item.priority` (smallest first).

        The type for this argument is aliased by `aqueue.Ordering`.

    :param bool graceful_ctrl_c: specifies whether pressing Ctrl-C will stop things
        abruptly (`False`) or wait until all items being processed by workers are
        finished first (`True`, the default).

        .. warning::

           If you write a buggy item that never finishes, Ctrl-C will have no effect.

    """

    trio.run(
        partial(
            async_run_queue,
            order=order,
            initial_items=initial_items,
            num_workers=num_workers,
            graceful_ctrl_c=graceful_ctrl_c,
        ),
        restrict_keyboard_interrupt_to_checkpoints=False,
    )
