import random
from typing import ClassVar

import trio

from aqueue import EnqueueFn, Item, SetDescFn, run_queue


class RootItem(Item):
    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        # display what we're doing in the worker status panel
        set_desc("Making child items")

        for _ in range(3):
            # simulate doing work and creating more items
            await trio.sleep(random.random())
            enqueue(ChildItem())

    async def after_children_processed(self) -> None:
        print("All done!")


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
