import pytest
from typing import Callable
import aqueue

# This is the same as using the @pytest.mark.anyio on all test functions in the module
pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "visualize",
    [
        True, False
    ],
)
async def test_queue_completes(visualize: bool):

    num_children = 5
    ran_children: list[bool] = []

    class RootItem(aqueue.Item):
        async def process(self) -> None:
            for _ in range(num_children):
                self.enqueue(ChildItem())

    class ChildItem(aqueue.Item):
        async def process(self) -> None:
            ran_children.append(True)

    await aqueue.async_run_queue(initial_items=[RootItem()], visualize=visualize)

    assert len(ran_children) == num_children


@pytest.mark.parametrize(
    "ordering, list_sort_fn",
    [
        ("fifo", list),
        ("lifo", lambda lst: list(reversed(lst))), # type: ignore
        ("priority", sorted),
    ],
)
@pytest.mark.parametrize(
    "visualize",
    [
        True, False
    ],
)
async def test_fifo_queue_ordering(
    ordering: aqueue.Ordering,
    list_sort_fn: Callable[[list[int]], list[int]],
    visualize: bool,
):

    ran_children: list[int] = []

    class AItem(aqueue.Item):
        priority = 1

        async def process(self) -> None:
            ran_children.append(self.priority)

    class BItem(aqueue.Item):
        priority = 2

        async def process(self) -> None:
            ran_children.append(self.priority)

    class CItem(aqueue.Item):
        priority = 3

        async def process(self) -> None:
            ran_children.append(self.priority)

    # some arbitrary, unordered order
    initial_items: list[aqueue.Item] = [
        BItem(),
        CItem(),
        AItem(),
        AItem(),
        CItem(),
        BItem(),
    ]

    await aqueue.async_run_queue(
        initial_items=initial_items,
        # for this test, its crucial to only have one worker, or else they may complete
        # out of order
        num_workers=1,
        order=ordering,
        visualize=visualize,
    )

    assert ran_children == list_sort_fn([item.priority for item in initial_items])
