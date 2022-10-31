from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from functools import partial
from typing import Literal, TypeAlias

import anyio
from attrs import field, frozen
from rich.console import Console

from aqueue.display import WAIT_MESSAGE, Display, LinkedTask
from aqueue.queue import QUEUE_FACTORY, Item, Ordering, QueueABC


@frozen(kw_only=True)
class Worker:
    queue: QueueABC[Item]
    graceful_ctrl_c: bool

    async def loop_for_items(self) -> None:
        async for item in self.queue:
            self.before_item_process(item)
            item._set_worker_desc = self.set_worker_desc

            def enqueue(child: Item) -> None:
                child.parent = item
                self.queue.put(child)
                item._children.append(child)
                self.on_child_enqueued(child)

            item._enqueue_fn = enqueue

            with anyio.CancelScope(shield=self.graceful_ctrl_c):
                await item.process()
                item._done_processing = True

                cur_item: Item | None = item
                while cur_item:
                    if not cur_item._tree_done:
                        break
                    await cur_item.after_children_processed()
                    cur_item = cur_item.parent

            item._enqueue_fn = None
            item._set_worker_desc = None

            self.after_item_process(item)
            self.queue.task_done()

        self.on_worker_complete()

    def before_item_process(self, item: Item) -> None:
        pass

    def set_worker_desc(self, description: str) -> None:
        pass

    def on_child_enqueued(self, item: Item) -> None:
        pass

    def after_item_process(self, item: Item) -> None:
        pass

    def on_worker_complete(self) -> None:
        pass


@frozen(kw_only=True)
class VisWorker(Worker):
    display: Display
    worker_status_task: LinkedTask

    def set_worker_desc(self, description: str) -> None:
        self.worker_status_task.description = description

    def before_item_process(self, item: Item) -> None:
        self.display.remove_from_queue(item)

    def on_child_enqueued(self, item: Item) -> None:
        self.display.add_to_queue(item)
        if item.track_overall:
            self.display.overall_task.total_f += 1

    def after_item_process(self, item: Item) -> None:
        if item.track_overall:
            self.display.overall_task.completed += 1
        self.worker_status_task.description = WAIT_MESSAGE

    def on_worker_complete(self) -> None:
        self.worker_status_task.description = "Done"


@frozen(kw_only=True)
class QueueRunner:
    num_workers: int = 5
    queue: QueueABC
    graceful_ctrl_c: bool = True

    @classmethod
    def _init_queue(
        cls,
        initial_items: Iterable[Item],
        order: Ordering,
    ) -> QueueABC:
        queue = QUEUE_FACTORY[order]()
        for item in initial_items:
            queue.put(item)
        return queue

    @classmethod
    def create(
        cls,
        initial_items: Iterable[Item],
        num_workers: int,
        order: Ordering,
        graceful_ctrl_c: bool,
    ) -> QueueRunner:
        queue = cls._init_queue(initial_items=initial_items, order=order)
        return QueueRunner(
            num_workers=num_workers, queue=queue, graceful_ctrl_c=graceful_ctrl_c
        )

    @asynccontextmanager
    async def outside_worker_loop_context(self) -> AsyncIterator[None]:
        """A context manager that is entered/exited outside the main worker loop."""
        yield

    def create_worker(self, worker_id: int) -> Worker:
        return Worker(queue=self.queue, graceful_ctrl_c=self.graceful_ctrl_c)

    def after_loop(self) -> None:
        pass

    async def run(self) -> None:
        async with self.outside_worker_loop_context():
            async with anyio.create_task_group() as worker_task_group:
                for worker_id in range(self.num_workers):
                    worker = self.create_worker(worker_id)
                    worker_task_group.start_soon(
                        worker.loop_for_items,
                        name=f"worker #{worker_id}",  # for debugging/introspection
                    )
        self.after_loop()


@frozen(kw_only=True)
class VisOptions:
    """
    A container for settings when visualizing the queue.
    """

    console: Console | None = field(default=None)
    """
    An explicit `rich.console.Console` to print the visualization. This should be
    provided if your are using a Console elsewhere in your code because it will conflict
    with aqueue's internal one.

    Setting this to `None` will use the console returned by `rich.get_console`.
    """


@frozen(kw_only=True)
class VisQueueRunner(QueueRunner):
    display: Display

    @classmethod
    def create(
        cls,
        initial_items: Iterable[Item],
        num_workers: int,
        order: Ordering,
        graceful_ctrl_c: bool,
        vis_options: VisOptions | None = None,
    ) -> VisQueueRunner:
        queue = cls._init_queue(initial_items=initial_items, order=order)

        console = None
        if vis_options and vis_options.console:
            console = vis_options.console

        display = Display.create(queue=queue, console=console)
        display.live.start()

        for item in initial_items:
            display.add_to_queue(item)
            if item.track_overall:
                display.overall_task.total_f += 1

        return VisQueueRunner(
            num_workers=num_workers,
            queue=queue,
            graceful_ctrl_c=graceful_ctrl_c,
            display=display,
        )

    @asynccontextmanager
    async def outside_worker_loop_context(self) -> AsyncIterator[None]:
        async with anyio.create_task_group() as live_refresher_task_group:
            live_refresher_task_group.start_soon(
                self.display.refresh_task, name="live-refresher"
            )
            yield
            live_refresher_task_group.cancel_scope.cancel()

    def create_worker(self, worker_id: int) -> Worker:
        return VisWorker(
            queue=self.queue,
            graceful_ctrl_c=self.graceful_ctrl_c,
            display=self.display,
            worker_status_task=self.display.create_worker_status_task(
                worker_id=worker_id
            ),
        )

    def after_loop(self) -> None:
        self.display.live.stop()


async def async_run_queue(
    *,
    initial_items: Iterable[Item],
    num_workers: int = 5,
    order: Ordering = "lifo",
    graceful_ctrl_c: bool = True,
    visualize: bool | VisOptions = True,
) -> None:
    """
    The coroutine of `aqueue.run_queue`. This function is useful if you want to bring
    your own event loop — either `asyncio` or `trio` event loops are usable with
    ``aqueue`` (those provided by `AnyIO <https://anyio.readthedocs.io/>`_).

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
    if visualize:
        vis_opions = visualize
        if vis_opions is True:
            vis_opions = VisOptions()

        runner: QueueRunner = VisQueueRunner.create(
            initial_items=initial_items,
            num_workers=num_workers,
            order=order,
            graceful_ctrl_c=graceful_ctrl_c,
            vis_options=vis_opions,
        )
    else:
        runner = QueueRunner.create(
            initial_items=initial_items,
            num_workers=num_workers,
            order=order,
            graceful_ctrl_c=graceful_ctrl_c,
        )

    await runner.run()


AsyncBackend: TypeAlias = Literal["trio", "asyncio"]


def run_queue(
    *,
    initial_items: Iterable[Item],
    num_workers: int = 5,
    order: Ordering = "lifo",
    graceful_ctrl_c: bool = True,
    visualize: bool | VisOptions = True,
    async_backend: AsyncBackend = "asyncio",
) -> None:
    """
    Process all items in ``initial_items`` (and any subsequent items they enqueue) until
    they are complete. Meanwhile, display a terminal visualization of it if
    ``visualize`` is not `False`.

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
        (`False`) or wait until all workers' current items have finished their process()
        methods and their after_children_processed() methods (`True`, the default). The
        latter will give you more opportunity to clean up resources, write data, etc.

        .. warning::

           If you write a buggy item that never finishes, Ctrl-C will have no effect.

    :param visualize: Set to `True` to draw a live progress meter display in the
        terminal while the queue is processed. Setting this to `False` does none of
        that.

        Further, you may pass an `aqueue.VisOptions` object here, which acts just like
        `True`, but lets you configure some things about how the visualization is
        performed.

    :param async_backend: Specified the asynchronous backend framework with which to run
        the event loop. Generally speaking, you may not mix-and-match event loops and
        the async primitives run inside them. Therefore, this argument lets you choose
        which one to use.

        The supported backends are those provided by `AnyIO`_.

    """

    anyio.run(
        partial(
            async_run_queue,
            order=order,
            initial_items=initial_items,
            num_workers=num_workers,
            graceful_ctrl_c=graceful_ctrl_c,
            visualize=visualize,
        ),
        backend=async_backend,
    )
