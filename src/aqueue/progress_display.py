from attrs import frozen

from aqueue._cvars import (
    OVERALL_PROGRESS_CVAR,
    OVERALL_PROGRESS_TASK_CVAR,
    WORKER_STATUS_PROGRESS_CVAR,
    WORKER_STATUS_PROGRESS_TASK_CVAR,
)


@frozen(kw_only=True)
class ProgressDisplay:
    """
    Provides access to the display. This is a thin wrapper around some
    rich.progress.Progress methods.
    """
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
        WORKER_STATUS_PROGRESS_CVAR.get().update(
            task_id=WORKER_STATUS_PROGRESS_TASK_CVAR.get(),
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
        OVERALL_PROGRESS_CVAR.get().advance(
            task_id=OVERALL_PROGRESS_TASK_CVAR.get(),
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
        OVERALL_PROGRESS_CVAR.get().update(
            task_id=OVERALL_PROGRESS_TASK_CVAR.get(),
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
        task = OVERALL_PROGRESS_CVAR.get()._tasks[OVERALL_PROGRESS_TASK_CVAR.get()]

        OVERALL_PROGRESS_CVAR.get().update(
            task_id=OVERALL_PROGRESS_TASK_CVAR.get(),
            total=(task.total or 0) + by,
        )
