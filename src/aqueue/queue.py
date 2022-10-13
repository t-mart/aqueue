from __future__ import annotations

import heapq
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import Generic, Literal, Type, TypeVar

import trio
from attrs import define, field

from aqueue.display import Display


class Item(ABC):
    """An abstract class for items."""

    @abstractmethod
    async def process(self, enqueue: EnqueueFn, progress_display: Display) -> None:
        """
        Do this items work. If any async primitives are to be used in this method, they
        must be compatible with trio.
        """


# type for the enqueue function
EnqueueFn = Callable[[Item], None]


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


# names a type of queue for the API
QueueTypeName = Literal["queue", "stack", "priority"]

QUEUE_FACTORY: dict[QueueTypeName, Type[Queue]] = {
    "queue": Queue,
    "stack": Stack,
    "priority": PriorityQueue,
}
