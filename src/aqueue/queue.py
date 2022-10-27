from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import ClassVar, Generic, Literal, TypeAlias, TypeVar

import anyio
from attrs import define, field
from sortedcontainers import SortedKeyList


@define
class Item(ABC):
    """
    The abstract class for items. Each subclass should represent one unit of work in
    your problem domain.
    """

    # _worker_status_task: LinkedTask | Literal[False] | None = None
    _set_worker_desc: Callable[[str], None] | None = field(default=None, init=False)
    _enqueue_fn: Callable[[Item], None] | None = field(default=None, init=False)

    @abstractmethod
    async def process(self) -> None:
        """
        Do this items work. This method is called when an item is popped from the queue.

        This method is required to be implemented.

        .. code-block:: python

            import aqueue

            class MyItem(aqueue.Item):
                async def process(self):
                    self.set_worker_desc("MyItem is processing...")

                    # do some work
                    ...

                    # enqueue more items
                    self.enqueue(Childitem())

            class ChildItem(aqueue.Item):
                async def process(self):
                    pass

        The return value for this method is aliased by `aqueue.ProcessRetVal`.
        """

    def enqueue(self, item: Item) -> None:
        """
        Enqueue another item for processing by a worker later. If this method is called
        outside of the process() method, it will raise a RuntimeError.

        :param item: The item to enqueue.
        """
        if self._enqueue_fn is None:
            raise RuntimeError("This function may only be called inside process()")
        self._enqueue_fn(item)

    def set_worker_desc(self, description: str) -> None:
        """
        Set the text description for the worker that is processing this item. If this
        method is called outside of the process() method, it will raise a RuntimeError.

        This method is a no-op if aqueue is not run with `run_queue`/`async_run_queue`
        is run with ``visualize=False``

        :param description: The text that the worker display will show.
        """
        if self._set_worker_desc is None:
            raise RuntimeError("This function may only be called inside process()")
        self._set_worker_desc(description)

    async def after_children_processed(self) -> None:
        """
        Do any kind of cleanup/finalization. This method is called after this item and
        all the child items enqueued by this item have returned from their ``process``
        method calls.

        The default implementation for this method is a no-op. Overriding it
        is optional.

        .. code-block:: python

            import aqueue

            class MyItem(aqueue.Item):
                async def after_children_processed(self):
                    print(f"{self} and all its children have been processed")
        """

    track_overall: ClassVar[bool] = False
    """
    Set this class variable to True to track it in the overall progress panel.

    If True, when this item is enqueued, the overall progress *total* will increment,
    and, when this item is done processing, the overall progress *completed* will
    increment.

    .. code-block:: python

        import aqueue

        class MyItem(aqueue.Item):
            track_overall = True
    """

    priority: ClassVar[int] = 0
    """
    Set this class variable to indicate priority.

    In priority queues, this number determines the ordering of how Item objects are
    popped from the queue for processing. Smaller numbers have higher priority.

    .. code-block:: python

        import aqueue

        class ImportantItem(aqueue.Item):
            priority = 1

        class PettyItem(aqueue.Item):
            priority = 2

    This attribute has no effect unless `run_queue`/`async_run_queue` is run with
    ``order="priority"``.
    """

    parent: Item | None = field(default=None, init=False)
    """
    The Item object that enqueued this one, or None if it was an initial item.

    This attribute is only valid inside ``process`` or after it has been called, such as
    in ``after_children_processed``. This attribute should not be overwritten or
    mutated.

    .. code-block:: python

        import aqueue

        class MyItem(aqueue.Item):
            async def process(self):
                parent = self.parent
                if not parent:
                    print("I'm an initial item")
                else:
                    print(f"I was created by {parent}")
    """

    _children: list[Item] = field(factory=list, init=False)
    """
    An internal list of Item objects that this item enqueued when it was processed.

    This is needed to keep track of children, which dictates when
    `after_children_processed` should be called.
    """

    _done_processing: bool = field(default=False, init=False)
    """
    An internal marker that is set to True when this method has completed processing.
    This is needed because, to properly trigger the `after_children_processed` callback,
    aqueue needs to know if an Item might still be processing.
    """

    @property
    def _tree_done(self) -> bool:
        """Return True if this Item and all its children have been processed."""
        return self._done_processing and all(
            child._tree_done for child in self._children
        )


# type for the return value of Item.process
ProcessRetVal: TypeAlias = AsyncIterator[Item] | None

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
            await anyio.sleep(0)
        return self._get()

    def empty(self) -> bool:
        return len(self) == 0

    def task_done(self) -> None:
        self._unfinished_task_count -= 1

    async def join(self) -> None:
        while self._unfinished_task_count != 0:
            await anyio.sleep(0)

    async def __aiter__(self) -> AsyncIterator[Item]:
        # gather 2 things: a get and a join
        not_changed = object()
        item: object | Item = not_changed

        async def join_and_cancel(cancel_scope: anyio.CancelScope) -> None:
            await self.join()
            cancel_scope.cancel()

        async def get_and_cancel(cancel_scope: anyio.CancelScope) -> None:
            nonlocal item
            item = await self.get()
            cancel_scope.cancel()

        while True:
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(join_and_cancel, task_group.cancel_scope)
                task_group.start_soon(get_and_cancel, task_group.cancel_scope)

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
    def key(value: Item) -> int:
        return value.priority

    return SortedKeyList(key=key)


@define
class PriorityQueue(QueueABC):
    """
    An unbounded priority queue. Items will need to set `priority` attributes
    appropriately.
    """

    _container: SortedKeyList = field(factory=_sortedkeylist_by_item)

    def _put(self, item: Item) -> None:
        self._container.add(item)

    def _get(self) -> Item:
        return self._container.pop(0)

    def __len__(self) -> int:
        return len(self._container)


# names a type of queue for the API
Ordering: TypeAlias = Literal["fifo", "lifo", "priority"]

QUEUE_FACTORY: dict[Ordering, type[QueueABC]] = {
    "fifo": Queue,
    "lifo": Stack,
    "priority": PriorityQueue,
}
