from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import ClassVar, Generic, Literal, Type, TypeVar

import trio
from attrs import define, field
from sortedcontainers import SortedKeyList

from aqueue.display import SetDescFn


@define
class Item(ABC):
    """
    The abstract class for items. Each subclass should represent one chunk of work in
    your problem domain.
    """

    track_overall: ClassVar[bool] = False
    """
    If True, when this item is enqueued, the overall progress *total* will increment,
    and, when this item is done processing, the overall progress *completed* will
    increment.
    """

    priority: ClassVar[int] = 0
    """
    In priority queues, this number determines the priority of this item. Smaller
    numbers have higher priority.
    """

    parent: Item | None = field(default=None)
    """
    The Item that enqueued this item, or None if it was an initial item.

    This attribute is only valid inside `process` or after it has been called. This
    attribute should not be overwritten or mutated.
    """

    _children: list[Item] = field(factory=list)
    """
    An internal list of Item objects that this item enqueued when it was processed.

    This is needed to keep track of children, which dictates when
    `after_children_processed` should be called.
    """

    _done_processing: bool = field(default=False)
    """
    An internal marker that is set to True when this method has completed processing.
    This is needed because, to properly trigger the `after_children_processed` callback,
    aqueue needs to know if an Item might still be processing.
    """

    @abstractmethod
    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        """
        Do this items work.

        Implementers should call the first arugment with any additional items to enqueue
        them for later processing. To provide good visual feedback, the second argument
        should be called with a description string.
        """

    async def _process(self, enqueue: EnqueueFn, set_worker_desc: SetDescFn) -> None:
        await self.process(enqueue, set_worker_desc)
        self._done_processing = True

    async def after_children_processed(self) -> None:
        """
        This method is called after all child items enqueued by this item are processed.
        Implementing this method is optional. Again, only trio-compatible primitives are
        allowed.

        Overriding ``Item``'s implementation for this method (a no-op) is optional.
        """

    @property
    def _tree_done(self) -> bool:
        """Return True if this Item and all its children have been processed."""
        return self._done_processing and all(
            child._tree_done for child in self._children
        )


# type for the enqueue function
EnqueueFn = Callable[[Item], None]


QueueContainer = TypeVar("QueueContainer")


@define
class QueueABC(ABC, Generic[QueueContainer]):

    _unfinished_task_count: int = field(init=False, default=0)

    @abstractmethod
    def _put(self, item: Item) -> None:
        ...

    @abstractmethod
    def _get(self) -> Item:
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...

    def put(self, item: Item) -> None:
        self._put(item)
        self._unfinished_task_count += 1

    async def get(self) -> Item:
        while self.empty():
            await trio.sleep(0)
        return self._get()

    def empty(self) -> bool:
        return len(self) == 0

    def task_done(self) -> None:
        self._unfinished_task_count -= 1

    async def join(self) -> None:
        while self._unfinished_task_count != 0:
            await trio.sleep(0)

    async def __aiter__(self) -> AsyncIterator[Item]:
        # gather 2 things: a get and a join
        not_changed = object()
        item: object | Item = not_changed

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
class Queue(QueueABC):
    """
    An unbounded FIFO queue
    """

    _container: deque[Item] = field(factory=deque)

    def _put(self, item: Item) -> None:
        self._container.appendleft(item)

    def _get(self) -> Item:
        return self._container.pop()

    def __len__(self) -> int:
        return len(self._container)


@define
class Stack(QueueABC):
    """
    An unbounded LIFO queue (or stack)
    """

    _container: list[Item] = field(factory=list)

    def _put(self, item: Item) -> None:
        self._container.append(item)

    def _get(self) -> Item:
        return self._container.pop()

    def __len__(self) -> int:
        return len(self._container)


def _sortedkeylist_by_item() -> SortedKeyList:
    def key(item: Item) -> int:
        return item.priority

    return SortedKeyList(key=key)


@define
class PriorityQueue(QueueABC):
    """
    An unbounded priority queue. Items will need to set `priority` attributes
    appropriately.
    """

    _container: SortedKeyList[Item] = field(factory=_sortedkeylist_by_item)

    def _put(self, item: Item) -> None:
        self._container.add(item)

    def _get(self) -> Item:
        return self._container.pop(0)

    def __len__(self) -> int:
        return len(self._container)


# names a type of queue for the API
QueueTypeName = Literal["queue", "stack", "priority"]

QUEUE_FACTORY: dict[QueueTypeName, Type[QueueABC]] = {
    "queue": Queue,
    "stack": Stack,
    "priority": PriorityQueue,
}
