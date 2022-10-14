from __future__ import annotations

import heapq
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import ClassVar, Literal, Type

import trio
from attrs import define, field

from aqueue.display import SetDescFn


class Item(ABC):
    """An abstract class for items."""

    # if True, when this item is
    track_overall: ClassVar[bool] = False

    @abstractmethod
    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        """
        Do this items work.

        Implementers should call the first arugment with any additional items to enqueue
        them for later processing. To provide good visual feedback, the second argument
        should be called with a description string.

        If any async primitives are to be used in this method, they must be compatible
        with trio.
        """

    async def after_children_processed(self) -> None:
        """
        This method is called after all child items enqueued by this item are processed.
        Implementing this method is optional. Again, only trio-compatible primitives are
        allowed.
        """


# type for the enqueue function
EnqueueFn = Callable[[Item], None]


@define(kw_only=True, hash=True)
class ItemNode:
    """
    This class lets us treat items like a tree.
    """

    # the item from the user
    item: Item

    # the parent to this item
    parent: ItemNode | None

    # any children this item created
    children: set[ItemNode] = field(factory=set, hash=False)

    # set to True only after the process method is complete. this is needed for because
    # we're in a concurrent environment and child may finish before their parent.
    done_processing: bool = field(default=False, hash=False)

    @property
    def tree_done(self) -> bool:
        return self.done_processing and all(child.tree_done for child in self.children)


@define
class Queue:
    """
    An unbounded FIFO queue
    """

    _container: deque[ItemNode] = field(init=False, factory=deque)
    _unfinished_task_count: int = field(init=False, default=0)

    def _put(self, item_node: ItemNode) -> None:
        self._container.appendleft(item_node)

    def _get(self) -> ItemNode:
        return self._container.pop()

    def put(self, item_node: ItemNode) -> None:
        self._put(item_node)
        self._unfinished_task_count += 1

    async def get(self) -> ItemNode:
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

    async def __aiter__(self) -> AsyncIterator[ItemNode]:
        # gather 2 things: a get and a join
        not_changed = object()
        item_node: object | ItemNode = not_changed

        async def join_and_cancel(cancel_scope: trio.CancelScope) -> None:
            await self.join()
            cancel_scope.cancel()

        async def get_and_cancel(cancel_scope: trio.CancelScope) -> None:
            nonlocal item_node
            item_node = await self.get()
            cancel_scope.cancel()

        while True:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(join_and_cancel, nursery.cancel_scope)
                nursery.start_soon(get_and_cancel, nursery.cancel_scope)

            if item_node is not_changed:
                return
            else:
                yield item_node  # type: ignore

            item_node = not_changed  # reset for next iter


@define
class Stack(Queue):
    """
    An unbounded LIFO queue (or stack)
    """

    def _put(self, item_node: ItemNode) -> None:
        self._container.append(item_node)


@define
class PriorityQueue(Queue):
    """
    An unbounded priority queue. Items will need to set their own ordering.
    """

    _container: deque[ItemNode] = field(init=False, factory=list)

    def _put(self, item_node: ItemNode) -> None:
        heapq.heappush(self._container, item_node)  # type: ignore

    def _get(self) -> ItemNode:
        return heapq.heappop(self._container)  # type: ignore


# names a type of queue for the API
QueueTypeName = Literal["queue", "stack", "priority"]

QUEUE_FACTORY: dict[QueueTypeName, Type[Queue]] = {
    "queue": Queue,
    "stack": Stack,
    "priority": PriorityQueue,
}
