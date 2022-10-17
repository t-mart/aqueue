import aqueue


class RootItem(aqueue.Item):
    async def process(
        self, enqueue: aqueue.EnqueueFn, set_desc: aqueue.SetDescFn
    ) -> None:
        # display what we're doing in the worker status panel
        set_desc("Processing RootItem")

        # make an HTTP request, parse it, etc
        ...

        # when you discover more items you want to process, enqueue them:
        for _ in range(5):
            enqueue(ChildItem())

    async def after_children_processed(self) -> None:
        # run this method when this Item and all other Items it enqueued are done
        print("All done!")


class ChildItem(aqueue.Item):

    # track the enqueueing and completion of these items in the overall panel
    track_overall: bool = True

    async def process(
        self, enqueue: aqueue.EnqueueFn, set_desc: aqueue.SetDescFn
    ) -> None:
        set_desc("Processing ChildItem")


if __name__ == "__main__":
    aqueue.run_queue(
        initial_items=[RootItem()],
        num_workers=2,
    )
