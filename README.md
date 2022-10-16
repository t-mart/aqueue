# aqueue

![demo](docs/demo.gif)

An async queue with live progress display. Good for running and visualizing tree-like I/O-bound
processing jobs, such as website scrapes.

## Example

```python
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

```

## Installation

```shell
pip install aqueue
```

## Usage Notes

There's two things you need to do to use aqueue:

1. Write your [Item](#items) classes
2. [Start your queue](#starting-your-queue) with one of those items

### Items

Items are your units of work. They can represent whatever you'd like, such as parts of a website
that you're trying to scrape: an item for the index page, for subpages, for images, etc.

Each item must be an instance of a subclass of `aqueue.Item`.

For example:

```python
from typing import ClassVar
import aqueue

class MyItem(aqueue.Item):
    async def process(self, enqueue: aqueue.EnqueueFn, set_desc: aqueue.SetDescFn) -> None:
        # display what we're doing in the worker status panel
        set_desc('Processing MyItem')

        # make an HTTP request, parse it, etc
        ...

        # when you discover more items you want to process, enqueue them:
        enqueue(AnotherItem())

class AnotherItem(aqueue.Item):

    track_overall: ClassVar[bool] = True

    async def process(self, enqueue: aqueue.EnqueueFn, set_desc: aqueue.SetDescFn) -> None:
        set_desc('Processing AnotherItem')
```

As a rule of thumb, you should make a new item class whenever you notice a one-to-many relationship.
For example, this _one_ page has _many_ images I want to download.

Note: `process` is async, but because this library uses
[Trio](https://trio.readthedocs.io/en/stable/index.html) under the hood, you may only use
Trio-compatible primitives inside `process`. For example, use `trio.sleep`, not `asyncio.sleep`.
TODO: consider [AnyIO](https://anyio.readthedocs.io/en/stable/) to avoid this problem?

Disclaimer: aqueue, or any asynchronous framework, is only going to be helpful if you're performing
work is I/O-bound.

#### `process` method, required

An item class must define an async `process` method. As arguments, it should accept two positional
arguments:

1. a `aqueue.EnqueueFn` that can be called to enqueue more work. That type is simply an alias for
   `Callable[[Item], None]`.
2. a `aqueue.SetDescFn` that can be called to update this worker's status with a string description.

#### `after_children_processed` method, optional

You can implement an `after_children_processed` method. After this item's `process` and any
(recursive) child's `process` are called, this method will be called.

#### `priority` property, optional

An int value that acts as the key when aqueue is running with `queue_type_name="priority"`. Smaller
numbers have higher priority.

#### `track_overall` property, optional

If set to True, when this item is enqueued, the Overall Progress total count increments. After its
process method completed, the Overall Progress completed count increments

### Starting your Queue

Then, start your queue with an initial item(s) to kick things off.

```python
aqueue.run_queue(
    initial_items=[MyItem()],
    num_workers=2,
    queue_type_name="stack",
    graceful_ctrl_c=True,
)
```

#### Queue type

By default, the queue is actually ...a queue -- that is to say that items are processed
first-in-first-out. Here are all the types you can specify with the `queue_type_name` argument.

- `queue` - first-in-first-out processing, or breadth-first.
- `stack` - last-in-first-out processing, or depth-first. This one is recommended for website
  scraping because it yields items fast (versus `queue` that tries to look at all the intermediate
  pages first).
- `priority` - priority queue processing. In this case, your item objects should be orderable (with
  `__lt__`, etc). **Lesser objects will be processed first**, because this code uses a minheap.

#### Number of workers

You can specify the number of workers you'd like to be processing your items with the `num_workers`
argument.

#### Ctrl-C

To stop your queue processing, press Ctrl-C.

If you've set the `graceful_ctrl_c` to False, this will stop the program immediately. If True, the
default, aqueue will wait for the items currently being worked on to complete (without taking any
additional items), and _then_ stop. Put another way, the choice is between responsiveness and
resource consistency.

### Sharing state

Often, its beneficial to share state between the items. Using the website scrape example again, you
may want to keep track of the URLs you've visited so you don't scrape them twice.

If this is needed, simply keep a global set/dict/list and store a key for the item. For example, a
URL string may be a good key.

If you don't want to or can't use a global variable, consider a
[`ContextVar`](https://docs.python.org/3/library/contextvars.html).

### Persisting state

During development, its probably likely that your program will crash after doing some work. For
example, maybe your HTTP request timed out or you had a bug in your HTML parsing.

It's a shame to lose that work that's been done. So, if you're looking for a really handy way to
persist state across runs, check out the built-in
[`shelve`](https://docs.python.org/3/library/shelve.html) module. It's like a dict that
automatically saves to a file each time you set a key in it.

### Other cool things

The API is fully docstringed and type-hinted 🥳
