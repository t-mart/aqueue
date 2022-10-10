from contextvars import ContextVar

from rich.progress import Progress, TaskID

OVERALL_PROGRESS_CVAR: ContextVar[Progress] = ContextVar("overall_progress")
OVERALL_PROGRESS_TASK_CVAR: ContextVar[TaskID] = ContextVar("overall_progress_task")
WORKER_STATUS_PROGRESS_CVAR: ContextVar[Progress] = ContextVar("worker_status_progress")
WORKER_STATUS_PROGRESS_TASK_CVAR: ContextVar[TaskID] = ContextVar(
    "worker_status_progress_task"
)