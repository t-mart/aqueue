from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, Any

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
    from aqueue.queue import QueueABC

WAIT_MESSAGE = "Waiting for work..."

SetDescFn = Callable[[str], None]


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


@frozen(kw_only=True)
class Display:
    """Internal display object that organizes away the complex setup of it all."""

    live: Live
    overall_task: LinkedTask
    queue_stats_task: LinkedTask
    worker_status_progress: Progress  # not a LinkedTask because workers wont yet exist

    @classmethod
    def create(cls) -> Display:
        worker_status_progress = Progress(
            SpinnerColumn(),
            TextColumn("[blue]{task.fields[worker_id]}"),
            TextColumn("[white]{task.description}"),
        )

        queue_stats_progress = Progress(
            SpinnerColumn(),
            TextColumn("[blue]Queue Size"),
            TextColumn("[white]{task.completed} items"),
            BarColumn(complete_style="cyan", finished_style="cyan"),
            TextColumn("[white]{task.total} items max"),
        )
        queue_stats_task = LinkedTask.create(progress=queue_stats_progress, total=0)

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
            live=live,
            overall_task=overall_task,
            worker_status_progress=worker_status_progress,
            queue_stats_task=queue_stats_task,
        )

    def create_update_queue_size_progress_fn(
        self, queue: QueueABC
    ) -> Callable[..., None]:
        # a perhaps-unintended use of a rich progress bar, which will move up/down
        # with the size of the queue and keep track of its maximum.
        def update_queue_size_progress() -> None:
            new_size = len(queue)
            old_max = self.queue_stats_task.task.total or 0

            self.queue_stats_task.update(
                completed=new_size,
                total=max(old_max, new_size),
            )

        return update_queue_size_progress

    def create_worker_status_task(
        self, worker_id: int, description: str = WAIT_MESSAGE
    ) -> LinkedTask:
        return LinkedTask.create(
            progress=self.worker_status_progress,
            description=description,
            worker_id=f"#{worker_id}",
        )
