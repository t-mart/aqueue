# NOTE: all this functionality is fake (it doesn't actually scrape a website). this is
# just an example to show a use case and implementation

import random
from contextvars import ContextVar

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

from aqueue import EnqueueFn, ProgressDisplay, run_queue, Item

# some piece of shared state that you want items to access
VISITED_VAR: ContextVar[set[str]] = ContextVar("visited")

NUM_PAGES = 5
NUM_IMAGES = 7


@frozen(kw_only=True)
class IndexItem(Item):
    """Represents the root level of the scrape"""

    async def process(
        self, enqueue: EnqueueFn, progress_display: ProgressDisplay
    ) -> None:
        progress_display.update_worker_desc("[blue]Scraping index at /images")

        for page in range(NUM_PAGES):
            # simulate page download and parse
            await trio.sleep(random.random())
            enqueue(PageItem(page=page))

        print("[yellow]Done scraping index")


@frozen(kw_only=True)
class PageItem(Item):
    """Represents a page on a website to scrape"""
    page: int

    async def process(
        self, enqueue: EnqueueFn, progress_display: ProgressDisplay
    ) -> None:
        progress_display.update_worker_desc(
            f"[cyan]scraping page at /images/{self.page}"
        )

        progress_display.incr_overall_total(NUM_IMAGES)

        for image in range(NUM_IMAGES):
            # simulate page download and parse
            await trio.sleep(random.random())
            enqueue(ImageItem(page=self.page, image=image))


@frozen(kw_only=True)
class ImageItem(Item):
    """Represents a image on a website to scrape"""
    page: int
    image: int

    async def process(
        self, enqueue: EnqueueFn, progress_display: ProgressDisplay
    ) -> None:
        image_path = f"/images/{self.page}/{self.image}"
        progress_display.update_worker_desc(f"[green]downloading image at {image_path}")

        if image_path in VISITED_VAR.get():
            # simulate skipping download
            print(f"[violet]Skipping image {image_path}")
        else:
            # simulate download
            await trio.sleep(random.random())

        progress_display.advance_overall()


def main() -> None:
    VISITED_VAR.set(
        {f"/images/{random.randint(0,NUM_PAGES-1)}/{random.randint(0,NUM_IMAGES-1)}"}
    )

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
