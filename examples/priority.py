from typing import ClassVar

from aqueue import Item, run_queue, ProcessRetVal


class AItem(Item):
    priority: ClassVar[int] = 1

    async def process(self) -> ProcessRetVal:
        print("A")


class BItem(Item):
    priority: ClassVar[int] = 2

    async def process(self) -> ProcessRetVal:
        print("B")


class CItem(Item):
    priority: ClassVar[int] = 3

    async def process(self) -> ProcessRetVal:
        print("C")


def main() -> None:
    run_queue(
        initial_items=[CItem(), BItem(), CItem(), AItem(), BItem(), AItem()],
        num_workers=1,
        order="priority",
    )


if __name__ == "__main__":
    main()
