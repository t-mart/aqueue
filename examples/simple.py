import random
from typing import ClassVar

import trio

from aqueue import EnqueueFn, Item, SetDescFn, run_queue


class RootItem(Item):
    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        num_children = 3
        set_desc("Making child items")

        for _ in range(num_children):
            # simulate doing work and creating more items
            await trio.sleep(random.random())
            enqueue(ChildItem())


class ChildItem(Item):
    # track these items on the Overall Progress panel
    track_overall: ClassVar[bool] = True

    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        set_desc("Doing work...")

        # Simulate doing work
        await trio.sleep(random.random())


def main() -> None:
    run_queue(
        initial_items=[RootItem()],
        num_workers=2,
    )


if __name__ == "__main__":
    main()
