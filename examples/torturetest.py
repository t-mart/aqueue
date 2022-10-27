# NOTE: all this functionality is fake (it doesn't actually scrape a website). this is
# just an example to show a use case and implementation

import asyncio
from typing import ClassVar
import random

from attrs import define
from rich import print

from aqueue import Item, run_queue

NUM_PAGES = 10
NUM_IMAGES = 7

# keep a list of previously downloaded things, in case of restarts
visited = {"http://example.com/images/1/2"}


@define(kw_only=True)
class IItem(Item):
    """Represents the root level of the scrape"""

    big: bool

    async def process(self) -> None:
        if self.big:
            self.set_worker_desc('big' * 40)
            print('big')
        else:
            self.set_worker_desc('small')
            print('small')
        await asyncio.sleep(1)

        if not random.randint(1,3) == 1:
            for _ in range(2):
                self.enqueue(IItem(big=not self.big))



def main() -> None:
    run_queue(
        initial_items=[IItem(big=True)],
        order="lifo",
        num_workers=5,
        graceful_ctrl_c=True,
    )


if __name__ == "__main__":
    main()
