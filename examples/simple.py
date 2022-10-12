import random

import trio

from aqueue import EnqueueFn, ProgressDisplay, run_queue, Item


class RootItem(Item):
    async def process(
        self, enqueue: EnqueueFn, progress_display: ProgressDisplay
    ) -> None:
        num_children = 3
        progress_display.update_worker_desc("Making child items")
        progress_display.set_overall_total(num_children)

        for _ in range(num_children):
            await trio.sleep(random.random())
            enqueue(ChildItem())


class ChildItem(Item):
    async def process(
        self, enqueue: EnqueueFn, progress_display: ProgressDisplay
    ) -> None:
        progress_display.update_worker_desc("Doing work...")
        await trio.sleep(random.random())


def main() -> None:
    run_queue(
        initial_items=[RootItem()],
        num_workers=2,
    )


if __name__ == "__main__":
    main()
