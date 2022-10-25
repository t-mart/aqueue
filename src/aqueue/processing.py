from __future__ import annotations

from collections.abc import Iterable
from functools import partial

import anyio

from aqueue.display import WAIT_MESSAGE, Display, LinkedTask
from aqueue.queue import QUEUE_FACTORY, Item, Ordering, Queue


async def _worker(
    queue: Queue,
    display: Display,
    worker_status_task: LinkedTask,
    graceful_ctrl_c: bool,
):
    async for item in queue:
        display.remove_from_queue(item)

        with anyio.CancelScope(shield=graceful_ctrl_c):
            item._worker_status_task = worker_status_task
            async for child in item._process():
                if child is None:
                    continue
                child.parent = item
                queue.put(child)
                display.add_to_queue(child)
                item._children.append(child)
                if child.track_overall:
                    display.overall_task.total_f += 1
            item._worker_status_task = None

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
    order: Ordering = "lifo",
    graceful_ctrl_c: bool = True,
) -> None:
    """
    The coroutine of `aqueue.run_queue`. This function is useful if you want to bring
    your own event loop — either `asyncio` or `trio` event loops are usable with
    ``aqueue`` (those provided by `AnyIO <https://anyio.readthedocs.io/>`__).

    The parameters for both functions are the same.

    .. code-block:: python

        import asyncio, aqueue

        class MyItem(aqueue.Item):
            async def process(self):
                pass

        asyncio.run(aqueue.async_run_queue(
            initial_items=[MyItem()],
        ))
    """
    queue = QUEUE_FACTORY[order]()

    display = Display.create(queue=queue)

    display.live.start()

    async with anyio.create_task_group() as task_group:
        for item in initial_items or []:
            queue.put(item)
            display.add_to_queue(item)
            if item.track_overall:
                display.overall_task.total_f += 1

        for worker_id in range(num_workers):
            worker_status_task = display.create_worker_status_task(worker_id=worker_id)

            task_group.start_soon(
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

    This function runs an `asyncio` event loop, which is the default provided by `AnyIO
    <https://anyio.readthedocs.io>`_. Use `async_run_queue` if you want to use a
    different event loop.

    .. code-block:: python

        import aqueue

        class MyItem(aqueue.Item):
            async def process(self):
                pass

        aqueue.run_queue(
            initial_items=[MyItem()],
        )

    :param initial_items: An iterable that seeds the queue. This is where the top-level
        item(s) should go that produces more items.

    :param num_workers: Specifies how many workers will be running concurrently.

        .. note::

           Setting a high ``num_workers`` does not automatically mean your program will
           run faster.

    :param order: Can be either of:

        - ``lifo`` for last-in-first-out processing, or depth-first. This is recommended
          for website scraping because it yields your deepest items fast, which are
          probably what you're really after (versus ``fifo`` that processes intermediate
          items first). This is the default.

        - ``fifo`` for first-in-first-out processing, or breadth-first.

        - ``priority`` for priority-based processing. In this case, processing will
          occur by *ascending* `Item.priority` (smallest first).

        .. note::

            ``priority`` only guarantees that workers will select items from the queue
            according to priority. It does not guarantee that items will be completed in
            any order.

        The type for this argument is aliased by `aqueue.Ordering`.

    :param graceful_ctrl_c: specifies whether pressing Ctrl-C will stop things abruptly
        (`False`) or wait until all items being processed by workers are finished first
        (`True`, the default).

        .. warning::

           If you write a buggy item that never finishes, Ctrl-C will have no effect.

    """

    anyio.run(
        partial(
            async_run_queue,
            order=order,
            initial_items=initial_items,
            num_workers=num_workers,
            graceful_ctrl_c=graceful_ctrl_c,
        ),
        # restrict_keyboard_interrupt_to_checkpoints=False,
    )
