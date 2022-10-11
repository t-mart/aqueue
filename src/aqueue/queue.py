from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Iterable, AsyncIterator
from functools import partial
from typing import cast, Generic, TypeVar
from collections import deque
from abc import ABC, abstractmethod
import heapq

import trio
from attrs import define, field
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from aqueue.progress_display import ProgressDisplay


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


# type for the enqueue function
EnqueueFn = Callable[[Item], Awaitable[None]]


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


ItemType = TypeVar("ItemType", bound=Item)


@define
class Queue(Generic[ItemType]):
    """
    An unbounded FIFO queue
    """

    _container: deque[ItemType] = field(init=False, factory=deque)
    _unfinished_task_count: int = field(init=False, default=0)

    def _put(self, item: ItemType) -> None:
        self._container.appendleft(item)

    def _get(self) -> ItemType:
        return self._container.pop()

    def put(self, item: ItemType) -> None:
        self._put(item)
        self._unfinished_task_count += 1

    async def get(self) -> ItemType:
        while self.empty():
            await trio.sleep(0)
        return self._get()

    def empty(self) -> bool:
        return not self._container

    def size(self) -> int:
        return len(self._container)

    def task_done(self) -> None:
        self._unfinished_task_count -= 1

    async def join(self) -> None:
        while self._unfinished_task_count != 0:
            await trio.sleep(0)

    async def __aiter__(self) -> AsyncIterator[ItemType]:
        # gather 2 things: a get and a join
        not_changed = object()
        item: object | ItemType = not_changed

        async def join_and_cancel(cancel_scope: trio.CancelScope) -> None:
            await self.join()
            cancel_scope.cancel()

        async def get_and_cancel(cancel_scope: trio.CancelScope) -> None:
            nonlocal item
            item = await self.get()
            cancel_scope.cancel()

        while True:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(join_and_cancel, nursery.cancel_scope)
                nursery.start_soon(get_and_cancel, nursery.cancel_scope)

            if item is not_changed:
                return
            else:
                yield item  # type: ignore

            item = not_changed  # reset for next iter


@define
class Stack(Queue, Generic[ItemType]):
    """
    An unbounded LIFO queue (or stack)
    """

    def _put(self, item: ItemType) -> None:
        self._container.append(item)

    def _get(self) -> ItemType:
        return self._container.pop()


@define
class PriorityQueue(Queue, Generic[ItemType]):
    """
    An unbounded priority queue. Items will need to set their own ordering.
    """

    _container: deque[ItemType] = field(init=False, factory=list)

    def _put(self, item: ItemType) -> None:
        heapq.heappush(self._container, item)  # type: ignore

    def _get(self) -> ItemType:
        return heapq.heappop(self._container)  # type: ignore


async def _worker(
    recv_channel: trio.MemoryReceiveChannel,
    enqueue: EnqueueFn,
    unfinished_tasks: _UnfinishedTasks,
    progress_display: ProgressDisplay,
):

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

    overall_progress_columns = overall_progress_columns or [
        SpinnerColumn(),
        TextColumn("[blue]{task.description}"),
        TaskProgressColumn(show_speed=True),
        TextColumn("[green]{task.completed}"),
        TimeElapsedColumn(),
        BarColumn(),
    ]
    overall_progress = Progress(*overall_progress_columns)
    overall_progress_task_id = overall_progress.add_task("Overall", total=None)

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

        for i in range(num_workers):
            worker_status_progress_task_id = worker_status_progress.add_task(
                _WAIT_MESSAGE, worker_id=f"#{i}"
            )
            progress_display = ProgressDisplay(
                overall_progress=overall_progress,
                overall_progress_task_id=overall_progress_task_id,
                worker_status_progress=worker_status_progress,
                worker_status_progress_task_id=worker_status_progress_task_id,
            )

            nursery.start_soon(
                partial(
                    _worker,
                    recv_channel=recv_channel,
                    enqueue=enqueue,
                    unfinished_tasks=unfinished_tasks,
                    progress_display=progress_display,
                ),
                name=f"worker #{i}",
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
