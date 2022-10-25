import aqueue


class RootItem(aqueue.Item):
    async def process(self) -> aqueue.ProcessRetVal:
        # display what we're doing in the worker status panel
        self.set_worker_desc("Processing RootItem")

        # make an HTTP request, parse it, etc
        ...

        # when you discover more items you want to process, enqueue them by yield-ing
        # them:
        for _ in range(3):
            yield ChildItem()

    async def after_children_processed(self) -> None:
        # run this method when this Item and all other Items it enqueued are done
        print("All done!")


class ChildItem(aqueue.Item):

    # track the enqueueing and completion of these items in the overall panel
    track_overall: bool = True

    async def process(self) -> aqueue.ProcessRetVal:
        self.set_worker_desc("Processing ChildItem")
        # this child item has no further children to enqueue, so it doesn't yield
        # anything


if __name__ == "__main__":
    aqueue.run_queue(
        initial_items=[RootItem()],
        num_workers=2,
    )
