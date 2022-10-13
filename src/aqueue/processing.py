from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial

import trio
from rich.progress import ProgressColumn

from aqueue.display import Display, DisplaySetuper
from aqueue.queue import QUEUE_FACTORY, Item, Queue, QueueTypeName

_WAIT_MESSAGE = "Waiting for work..."


async def _worker(
    queue: Queue[Item],
    progress_display: Display,
    update_queue_size_progress: Callable[..., None],
):
    async for item in queue:
        with trio.CancelScope(shield=True):  # let them finish cleanly in case error
            await item.process(queue.put, progress_display)
        progress_display.worker.description = _WAIT_MESSAGE
        update_queue_size_progress()
        queue.task_done()

    progress_display.worker.description = "Done"


async def async_run_queue(
    *,
    queue_type_name: QueueTypeName,
    overall_progress_columns: Iterable[ProgressColumn] | None = None,
    initial_items: Iterable[Item] | None = None,
    num_workers: int = 10,
) -> None:
    """
    An asynchronous version of `run_queue`. This method must be run in a Trio event
    loop.
    """
    queue = QUEUE_FACTORY[queue_type_name]()

    display = DisplaySetuper.create(
        overall_progress_columns=overall_progress_columns or []
    )
    update_queue_size_progress = display.create_update_queue_size_progress_fn(queue)

    display.live.start()

    async with trio.open_nursery() as nursery:
        for item in initial_items or []:
            queue.put(item)

        for i in range(num_workers):
            worker_status_progress_task_id = display.worker_status_progress.add_task(
                _WAIT_MESSAGE, worker_id=f"#{i}"
            )
            progress_display = display.create_progress_display(
                worker_status_progress_task_id
            )

            nursery.start_soon(
                partial(
                    _worker,
                    queue=queue,
                    progress_display=progress_display,
                    update_queue_size_progress=update_queue_size_progress,
                ),
                name=f"worker #{i}",
            )

    display.live.stop()


def run_queue(
    *,
    num_workers: int = 10,
    initial_items: Iterable[Item] | None = None,
    queue_type_name: QueueTypeName = "queue",
    overall_progress_columns: Iterable[ProgressColumn] | None = None,
    restrict_ctrl_c_to_checkpoints: bool = False,
) -> None:
    """
    Process all items in initial items (and any subsequent items they produce) and
    display a terminal visualization of it.

    - `num_workers` specifies how many workers will be running concurrently
    - `initial_items` is an iterable that seeds the queue. This is where the top-level
      item should go that produces more items. (Note that any subsequent item can also
      produce items.)
    - `queue_type_name` can be either of:
      - `queue` for first-in-first-out processing
      - `stack` for last-in-first-out processing
      - `priority` for priority-based processing. In this case, item objects should be
        orderable. Processing will occur in *ascending* priority (smallest first).
    - `overall_progress_columns` is an iterable of columns for the "Overall Progress"
      panel. These must be `rich.progress.ProgressColumn` objects. See
      https://rich.readthedocs.io/en/stable/progress.html#columns.
    - `restrict_ctrl_c_to_checkpoints` specifies whether pressing Ctrl-C will cancel
      things abruptly (False) or wait until a "checkpoint" (True). See
      https://trio.readthedocs.io/en/stable/reference-core.html#trio.run
    """

    trio.run(
        partial(
            async_run_queue,
            queue_type_name=queue_type_name,
            initial_items=initial_items,
            overall_progress_columns=overall_progress_columns,
            num_workers=num_workers,
        ),
        restrict_keyboard_interrupt_to_checkpoints=restrict_ctrl_c_to_checkpoints,
    )
