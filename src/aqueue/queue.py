from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Iterable
from functools import partial
from typing import cast
from abc import ABC, abstractmethod

import trio
from attrs import define, field
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from aqueue.progress_display import ProgressDisplay
from aqueue._cvars import (
    OVERALL_PROGRESS_CVAR,
    OVERALL_PROGRESS_TASK_CVAR,
    WORKER_STATUS_PROGRESS_CVAR,
    WORKER_STATUS_PROGRESS_TASK_CVAR,
)

_WAIT_MESSAGE = "Waiting for work..."


class Item(ABC):
    """An abstract class for items."""

    @abstractmethod
    async def process(
        self, enqueue: EnqueueFn, progress_display: ProgressDisplay
    ) -> None:
        """
        Do this items work. If any async primitives are to be used in this method, they
        must be compatible with trio.
        """


@define(kw_only=True)
class _UnfinishedTasks:
    _count: int = field(init=False, default=0)
    _event: trio.Event

    def incr(self) -> None:
        self._count += 1

    def decr(self) -> None:
        # only on decr can the event be set (which means newly created UnfinishedTasks
        # with zero counts won't trigger it)
        self._count -= 1
        if self._count == 0:
            self._event.set()


# type for the enqueue function
EnqueueFn = Callable[[Item], Awaitable[None]]


async def _worker(
    recv_channel: trio.MemoryReceiveChannel,
    enqueue: EnqueueFn,
    unfinished_tasks: _UnfinishedTasks,
    progress_display: ProgressDisplay,
    worker_status_progress_task: TaskID,
):
    # now that we're in our worker, set its progress task
    WORKER_STATUS_PROGRESS_TASK_CVAR.set(worker_status_progress_task)

    async with recv_channel:
        async for item in recv_channel:
            with trio.CancelScope(shield=True):  # let them finish cleanly in case error
                item = cast(Item, item)
                await item.process(enqueue, progress_display)
            progress_display.update_worker_desc(_WAIT_MESSAGE)
            unfinished_tasks.decr()

    progress_display.update_worker_desc("Done")


async def _async_run_queue(
    *,
    overall_progress_columns: Iterable[ProgressColumn] | None = None,
    initial_items: Iterable[Item] | None = None,
    num_workers: int = 10,
) -> None:
    worker_status_progress = Progress(
        SpinnerColumn(),
        TextColumn("[blue]{task.fields[worker_id]}"),
        TextColumn("[white]{task.description}"),
    )
    WORKER_STATUS_PROGRESS_CVAR.set(worker_status_progress)
    worker_status_progress_tasks = [
        worker_status_progress.add_task(_WAIT_MESSAGE, worker_id=f"#{i}")
        for i in range(num_workers)
    ]

    overall_progress_columns = overall_progress_columns or [
        SpinnerColumn(),
        TextColumn("[blue]{task.description}"),
        TaskProgressColumn(show_speed=True),
        TextColumn("[green]{task.completed}"),
        TimeElapsedColumn(),
        BarColumn(),
    ]
    overall_progress = Progress(*overall_progress_columns)
    overall_progress_task = overall_progress.add_task("Overall", total=None)
    OVERALL_PROGRESS_CVAR.set(overall_progress)
    OVERALL_PROGRESS_TASK_CVAR.set(overall_progress_task)

    table = Table.grid()
    table.add_row(Panel(worker_status_progress, title="Worker Status"))
    table.add_row(Panel(overall_progress, title="Overall Progress"))

    live = Live(table)
    live.start()

    async with trio.open_nursery() as nursery:
        send_channel, recv_channel = trio.open_memory_channel(math.inf)

        done_event = trio.Event()

        unfinished_tasks = _UnfinishedTasks(event=done_event)

        async def enqueue(item: Item) -> None:
            unfinished_tasks.incr()
            await send_channel.send(item)

        for item in initial_items or []:
            await enqueue(item)

        progress_display = ProgressDisplay()

        for i, worker_status_progress_task in enumerate(worker_status_progress_tasks):
            name = f"worker #{i}"
            nursery.start_soon(
                partial(
                    _worker,
                    recv_channel=recv_channel,
                    enqueue=enqueue,
                    unfinished_tasks=unfinished_tasks,
                    worker_status_progress_task=worker_status_progress_task,
                    progress_display=progress_display,
                ),
                name=name,
            )

        await done_event.wait()
        await send_channel.aclose()

    live.stop()


def run_queue(
    *,
    num_workers: int = 10,
    initial_items: Iterable[Item] | None = None,
    overall_progress_columns: Iterable[ProgressColumn] | None = None,
    restrict_ctrl_c_to_checkpoints: bool = False,
) -> None:
    """
    Process all items in an async FIFO queue and display output of that processing in
    a live display.

    - `num_workers` specifies how many workers will be running concurrently
    - `initial_items` is an iterable that seeds the queue. This is where the top-level
      item should go that produces more items. (Note that any subsequent item can also
      produce items.)
    - `overall_progress_columns` is an iterable of columns for the "Overall Progress"
      panel. These must be `rich.progress.ProgressColumn` objects. See
      https://rich.readthedocs.io/en/stable/progress.html#columns.
    - `restrict_ctrl_c_to_checkpoints` specifies whether pressing Ctrl-C will cancel
      things abruptly (False) or wait until a "checkpoint" (True). See
      https://trio.readthedocs.io/en/stable/reference-core.html#trio.run
    """

    trio.run(
        partial(
            _async_run_queue,
            initial_items=initial_items,
            overall_progress_columns=overall_progress_columns,
            num_workers=num_workers,
        ),
        restrict_keyboard_interrupt_to_checkpoints=restrict_ctrl_c_to_checkpoints,
    )
