from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import cached_property, wraps
from typing import TYPE_CHECKING

from attrs import define, frozen
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

if TYPE_CHECKING:
    # avoid circular reference when just trying to type hint
    from aqueue.queue import Queue


@frozen(kw_only=True)
class DisplaySetuper:
    """Internal display object that organizes away the complex setup of it all"""

    live: Live
    overall_progress: Progress
    overall_progress_task_id: TaskID
    worker_status_progress: Progress
    queue_stats_progress: Progress
    queue_stats_progress_task_id: TaskID

    @classmethod
    def create(
        cls, overall_progress_columns: Iterable[ProgressColumn]
    ) -> DisplaySetuper:
        worker_status_progress = Progress(
            SpinnerColumn(),
            TextColumn("[blue]{task.fields[worker_id]}"),
            TextColumn("[white]{task.description}"),
        )

        queue_stats_progress = Progress(
            SpinnerColumn(),
            TextColumn("[blue]Stack Size"),
            TextColumn("[white]{task.completed} items"),
            BarColumn(complete_style="cyan", finished_style="cyan"),
            TextColumn("[white]{task.total} items max"),
        )
        queue_stats_progress_task_id = queue_stats_progress.add_task("", total=0)

        overall_progress_columns = overall_progress_columns or [
            SpinnerColumn(),
            TextColumn("[blue]{task.description}"),
            TaskProgressColumn(show_speed=True),
            TextColumn("[green]{task.completed}"),
            TimeElapsedColumn(),
            BarColumn(),
        ]
        overall_progress = Progress(*overall_progress_columns)
        overall_progress_task_id = overall_progress.add_task("Overall", total=None)

        table = Table.grid()
        table.add_row(Panel(worker_status_progress, title="Worker Status"))
        table.add_row(Panel(queue_stats_progress, title="Queue Stats"))
        table.add_row(Panel(overall_progress, title="Overall Progress"))

        live = Live(table)

        return DisplaySetuper(
            live=live,
            overall_progress=overall_progress,
            overall_progress_task_id=overall_progress_task_id,
            worker_status_progress=worker_status_progress,
            queue_stats_progress=queue_stats_progress,
            queue_stats_progress_task_id=queue_stats_progress_task_id,
        )

    def create_update_queue_size_progress_fn(self, queue: Queue) -> Callable[..., None]:
        def update_queue_size_progress() -> None:
            new_size = queue.size()
            old_max = (
                self.queue_stats_progress._tasks[
                    self.queue_stats_progress_task_id
                ].total
                or 0
            )

            self.queue_stats_progress.update(
                task_id=self.queue_stats_progress_task_id,
                completed=new_size,
                total=max(old_max, new_size),
            )

        return update_queue_size_progress

    def create_progress_display(
        self, worker_status_progress_task_id: TaskID
    ) -> Display:
        return Display(
            worker=WorkerStatus(
                linked_task=LinkedTask(
                    progress=self.worker_status_progress,
                    task_id=worker_status_progress_task_id,
                ),
            ),
            overall=Overall(
                linked_task=LinkedTask(
                    progress=self.overall_progress,
                    task_id=self.overall_progress_task_id,
                )
            ),
        )


@frozen(kw_only=True, slots=False)
class LinkedTask:
    """
    A progress and a task, linked together. This makes the rich API easier to work with
    because only one thing needs to be passed around, not two.
    """

    progress: Progress
    task_id: TaskID

    @cached_property
    def task(self) -> Task:
        # yeesh, hacky. rich has questionable interface here
        return self.progress._tasks[self.task_id]

    @wraps(Progress.update)
    def update(self, **kwargs) -> None:
        self.progress.update(task_id=self.task_id, **kwargs)


@define(kw_only=True)
class Overall:
    """Represents the "Overall Progress" display."""

    _linked_task: LinkedTask

    @property
    def completed(self) -> float:
        """Get the amount of completed items"""
        return self._linked_task.task.completed

    @completed.setter
    def completed(self, value: float) -> None:
        """Set the amount of completed items"""
        self._linked_task.update(completed=value)

    @property
    def total(self) -> float | None:
        """Get the amount of total items"""
        return self._linked_task.task.total

    @total.setter
    def total(self, value: float | None) -> None:
        """Set the amount of total items"""
        self._linked_task.update(total=value)

    @property
    def total_f(self) -> float:
        """Get the amount of total items. If the total is actually None, return 0."""
        return self._linked_task.task.total or 0

    @total_f.setter
    def total_f(self, value: float) -> None:
        """Set the amount of total items. (Setter paired with total_f.)"""
        self._linked_task.update(total=value)


@define(kw_only=True)
class WorkerStatus:
    """Represents the current worker display."""

    _linked_task: LinkedTask

    @property
    def description(self) -> str:
        """Get the current worker status description"""
        return self._linked_task.task.description

    @description.setter
    def description(self, value: str) -> None:
        """Set the current worker status description"""
        self._linked_task.update(description=value)


@frozen(kw_only=True)
class Display:
    """
    Provides access to queue items to update the display. This is a thin wrapper around
    some rich.progress.Progress methods.
    """

    worker: WorkerStatus
    overall: Overall
