import random

import trio

from aqueue import Display, EnqueueFn, Item, run_queue


class RootItem(Item):
    async def process(self, enqueue: EnqueueFn, display: Display) -> None:
        num_children = 3
        display.overall.total = num_children
        display.worker.description = "Making child items"

        for _ in range(num_children):
            # simulate doing work and creating more items
            await trio.sleep(random.random())
            enqueue(ChildItem())


class ChildItem(Item):
    async def process(self, enqueue: EnqueueFn, display: Display) -> None:
        display.worker.description = "Doing work..."

        # Simulate doing work
        await trio.sleep(random.random())

        display.overall.completed += 1


def main() -> None:
    run_queue(
        initial_items=[RootItem()],
        num_workers=2,
    )


if __name__ == "__main__":
    main()
