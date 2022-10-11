from attrs import frozen
from rich.progress import Progress, TaskID


@frozen(kw_only=True)
class ProgressDisplay:
    """
    Provides access to the display. This is a thin wrapper around some
    rich.progress.Progress methods.
    """
    _overall_progress: Progress
    _overall_progress_task_id: TaskID
    _worker_status_progress: Progress
    _worker_status_progress_task_id: TaskID

    def update_worker_desc(self, desc: str) -> None:
        """
        Update the worker's status.

        Equivalent to calling

        ```
        Progress.update(
            task_id=<current_worker_task>,
            description=desc
        )
        ```
        """
        self._worker_status_progress.update(
            task_id=self._worker_status_progress_task_id,
            description=desc,
        )

    def advance_overall(self, by: int = 1) -> None:
        """
        Advance the overall completed items by an amount.

        Equivalent to calling

        ```
        Progress.advance(
            task_id=<current_worker_task>,
            advance=by
        )
        ```
        """
        self._overall_progress.advance(
            task_id=self._overall_progress_task_id,
            advance=by,
        )

    def set_overall_total(self, to: int) -> None:
        """
        Advance the overall completed items to an amount.

        Equivalent to calling

        ```
        Progress.update(
            task_id=<current_worker_task>,
            total=to
        )
        ```
        """
        self._overall_progress.update(
            task_id=self._overall_progress_task_id,
            total=to,
        )

    def incr_overall_total(self, by: int = 1) -> None:
        """
        Increment the overall completed items by an amount. Useful for when you're
        discovering new items over a course of actions.

        Equivalent to calling

        ```
        Progress.update(
            task_id=<current_worker_task>,
            total=<old_total> + by
        )
        ```
        """
        # yeesh, hacky. rich has questionable interface here
        task = self._overall_progress._tasks[self._overall_progress_task_id]

        self._overall_progress.update(
            task_id=self._overall_progress_task_id,
            total=(task.total or 0) + by,
        )
