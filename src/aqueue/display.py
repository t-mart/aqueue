from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, Any, TypeAlias

from attrs import define, frozen
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    Task,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

if TYPE_CHECKING:
    # avoid circular reference when just trying to type hint
    from aqueue.queue import Item, QueueABC

WAIT_MESSAGE = "Waiting for work..."

# something obscure to not clash with user names
TOTAL_QUEUE_COUNT_NAME = "_aqueue_total"

SetDescFn: TypeAlias = Callable[[str], None]


@define(kw_only=True, slots=False)
class LinkedTask:
    """
    A progress and a task, linked together. This makes the rich API easier to work with
    because only one thing needs to be passed around, not two.
    """

    progress: Progress
    task_id: TaskID

    @classmethod
    def create(cls, progress: Progress, **kwargs: Any) -> LinkedTask:
        description = ""
        if "description" in kwargs:
            description = kwargs.pop("description")

        task_id = progress.add_task(description=description, **kwargs)

        return LinkedTask(progress=progress, task_id=task_id)

    @cached_property
    def task(self) -> Task:
        # yeesh, hacky. rich has questionable interface here
        return self.progress._tasks[self.task_id]

    def update(self, **kwargs: Any) -> None:
        self.progress.update(task_id=self.task_id, **kwargs)

    # convenience properties
    @property
    def completed(self) -> float:
        """Get the amount of completed items"""
        return self.task.completed

    @completed.setter
    def completed(self, value: float) -> None:
        """Set the amount of completed items"""
        self.update(completed=value)

    @property
    def total(self) -> float | None:
        """Get the amount of total items"""
        return self.task.total

    @total.setter
    def total(self, value: float | None) -> None:
        """Set the amount of total items"""
        self.update(total=value)

    @property
    def total_f(self) -> float:
        """Get the amount of total items. If the total is actually None, return 0."""
        return self.task.total or 0

    @total_f.setter
    def total_f(self, value: float) -> None:
        """Set the amount of total items. (Setter paired with total_f.)"""
        self.update(total=value)

    @property
    def description(self) -> str:
        """Get the current worker status description"""
        return self.task.description

    @description.setter
    def description(self, value: str) -> None:
        """Set the current worker status description"""
        self.update(description=value)


@define(kw_only=True)
class QueueItemCount:
    linked_task: LinkedTask

    @classmethod
    def create(cls, progress: Progress, name: str) -> QueueItemCount:
        linked_task = LinkedTask.create(progress, total=0, name=name)
        return QueueItemCount(linked_task=linked_task)

    @property
    def cur_count(self) -> float:
        return self.linked_task.completed

    @cur_count.setter
    def cur_count(self, value: int) -> None:
        self.linked_task.completed = value
        self.linked_task.total_f = max(value, self.linked_task.total_f)


@frozen(kw_only=True)
class Display:
    """Internal display object that organizes away the complex setup of it all."""

    queue: QueueABC
    live: Live
    overall_task: LinkedTask
    queue_stats_progress: Progress
    queue_stats_type_tasks: dict[str, QueueItemCount]
    worker_status_progress: Progress  # not a LinkedTask because workers wont yet exist

    @classmethod
    def create(cls, queue: QueueABC) -> Display:
        worker_status_progress = Progress(
            SpinnerColumn(),
            TextColumn("[blue]{task.fields[worker_id]}"),
            TextColumn("[white]{task.description}"),
        )

        queue_stats_progress = Progress(
            SpinnerColumn(),
            TextColumn("[blue]{task.fields[name]}"),
            TextColumn("[white]{task.completed} items cur"),
            BarColumn(complete_style="cyan", finished_style="cyan"),
            TextColumn("[white]{task.total} items max"),
        )
        queue_stats_type_tasks = {
            TOTAL_QUEUE_COUNT_NAME: QueueItemCount.create(
                queue_stats_progress, name="Total"
            )
        }

        overall_progress = Progress(
            SpinnerColumn(),
            TextColumn("[blue]{task.description}"),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )
        overall_task = LinkedTask.create(progress=overall_progress, total=None)

        table = Table.grid()
        table.add_row(Panel(worker_status_progress, title="Worker Status"))
        table.add_row(Panel(queue_stats_progress, title="Queue Stats"))
        table.add_row(Panel(overall_progress, title="Overall Progress"))

        live = Live(table)

        return Display(
            queue=queue,
            live=live,
            overall_task=overall_task,
            worker_status_progress=worker_status_progress,
            queue_stats_progress=queue_stats_progress,
            queue_stats_type_tasks=queue_stats_type_tasks,
        )

    def create_worker_status_task(
        self, worker_id: int, description: str = WAIT_MESSAGE
    ) -> LinkedTask:
        return LinkedTask.create(
            progress=self.worker_status_progress,
            description=description,
            worker_id=f"#{worker_id}",
        )

    def add_to_queue(self, item: Item) -> None:
        self.queue_stats_type_tasks[TOTAL_QUEUE_COUNT_NAME].cur_count += 1

        item_class_name = item.__class__.__qualname__
        if item_class_name not in self.queue_stats_type_tasks:
            self.queue_stats_type_tasks[item_class_name] = QueueItemCount.create(
                self.queue_stats_progress, item_class_name
            )

        self.queue_stats_type_tasks[item_class_name].cur_count += 1

    def remove_from_queue(self, item: Item) -> None:
        self.queue_stats_type_tasks[TOTAL_QUEUE_COUNT_NAME].cur_count -= 1
        self.queue_stats_type_tasks[item.__class__.__qualname__].cur_count -= 1
