import pytest
from typing import Callable
import aqueue

# This is the same as using the @pytest.mark.anyio on all test functions in the module
pytestmark = pytest.mark.anyio


async def test_queue_completes():

    num_children = 5
    ran_children = []

    class RootItem(aqueue.Item):
        async def process(self) -> aqueue.ProcessRetVal:
            for _ in range(num_children):
                yield ChildItem()

    class ChildItem(aqueue.Item):
        async def process(self) -> aqueue.ProcessRetVal:
            ran_children.append(True)

    await aqueue.async_run_queue(initial_items=[RootItem()])

    assert len(ran_children) == num_children


@pytest.mark.parametrize(
    "ordering, list_sort_fn",
    [
        ("fifo", list),
        ("lifo", lambda l: list(reversed(l))),
        ("priority", sorted),
    ],
)
async def test_fifo_queue_ordering(
    ordering: aqueue.Ordering,
    list_sort_fn: Callable[[list[int]], list[int]],
):

    ran_children = []

    class AItem(aqueue.Item):
        priority = 1

        async def process(self) -> aqueue.ProcessRetVal:
            ran_children.append(self.priority)

    class BItem(aqueue.Item):
        priority = 2

        async def process(self) -> aqueue.ProcessRetVal:
            ran_children.append(self.priority)

    class CItem(aqueue.Item):
        priority = 3

        async def process(self) -> aqueue.ProcessRetVal:
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
    )

    assert ran_children == list_sort_fn([item.priority for item in initial_items])
