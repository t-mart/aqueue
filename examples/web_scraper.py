# NOTE: all this functionality is fake (it doesn't actually scrape a website). this is
# just an example to show a use case and implementation

import random
from typing import ClassVar

import trio
from attrs import frozen
from rich import print
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from aqueue import Display, EnqueueFn, Item, run_queue

NUM_PAGES = 5
NUM_IMAGES = 7

# keep a list of previously downloaded things, in case of restarts
visited = {"/images/1/2"}


@frozen(kw_only=True)
class IndexItem(Item):
    """Represents the root level of the scrape"""

    URL: ClassVar[str] = "http://example.com/images"

    async def process(self, enqueue: EnqueueFn, display: Display) -> None:
        display.worker.description = f"[blue]Scraping index at {self.URL}"

        # simulate page download and parse
        await trio.sleep(random.random())

        for page_number in range(NUM_PAGES):
            enqueue(PageItem(url=f"{self.URL}/{page_number}"))

        print("[yellow]Done scraping index")


@frozen(kw_only=True)
class PageItem(Item):
    """Represents a page on a website to scrape"""

    url: str

    async def process(self, enqueue: EnqueueFn, display: Display) -> None:
        display.worker.description = f"[cyan]scraping page at {self.url}"
        display.overall.total_f += NUM_IMAGES

        for image_number in range(NUM_IMAGES):
            # simulate page download and parse
            await trio.sleep(random.random())
            enqueue(ImageItem(url=f"{self.url}/{image_number}"))


@frozen(kw_only=True)
class ImageItem(Item):
    """Represents a image on a website to scrape"""

    url: str

    async def process(self, enqueue: EnqueueFn, display: Display) -> None:
        display.worker.description = f"[green]downloading image at {self.url}"

        if self.url not in visited:
            # simulate download
            await trio.sleep(random.random())
            visited.add(self.url)
        else:
            # simulate skipping download because it's already been downloaded
            print(f"[violet]Skipping image {self.url}")

        display.overall.completed += 1


def main() -> None:
    run_queue(
        initial_items=[IndexItem()],
        queue_type_name="stack",
        num_workers=5,
        overall_progress_columns=[
            SpinnerColumn(),
            TextColumn("[blue]{task.description}"),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ],
        restrict_ctrl_c_to_checkpoints=True,
    )


if __name__ == "__main__":
    main()
