# NOTE: all this functionality is fake (it doesn't actually scrape a website). this is
# just an example to show a use case and implementation

import random
from typing import ClassVar

import trio
from attrs import define
from rich import print

from aqueue import EnqueueFn, Item, SetDescFn, run_queue

NUM_PAGES = 10
NUM_IMAGES = 7

# keep a list of previously downloaded things, in case of restarts
visited = {"http://example.com/images/1/2"}


@define(kw_only=True)
class Index(Item):
    """Represents the root level of the scrape"""

    URL: ClassVar[str] = "http://example.com/images"

    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        set_desc(f"[blue]Scraping index at {self.URL}")

        # simulate page download and parse
        await trio.sleep(random.random())

        for page_number in range(NUM_PAGES):
            enqueue(Page(url=f"{self.URL}/{page_number}"))

        print("[yellow]Done scraping index")

    async def after_children_processed(self) -> None:
        print("All done!")


@define(kw_only=True)
class Page(Item):
    """Represents a page on a website to scrape"""

    url: str

    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        set_desc(f"[cyan]scraping page at {self.url}")

        for image_number in range(NUM_IMAGES):
            # simulate page download and parse
            await trio.sleep(random.random())
            enqueue(Image(url=f"{self.url}/{image_number}"))


@define(kw_only=True)
class Image(Item):
    """Represents a image on a website to scrape"""

    url: str

    track_overall: ClassVar[bool] = True

    async def process(self, enqueue: EnqueueFn, set_desc: SetDescFn) -> None:
        set_desc(f"[green]downloading image at {self.url} from {self.parent.url}")

        if self.url not in visited:
            # simulate download
            await trio.sleep(random.random())
            visited.add(self.url)
        else:
            # simulate skipping download because it's already been downloaded
            print(f"[violet]Skipping image {self.url}")


def main() -> None:
    run_queue(
        initial_items=[Index()],
        order="lifo",
        num_workers=5,
        graceful_ctrl_c=True,
    )


if __name__ == "__main__":
    main()
