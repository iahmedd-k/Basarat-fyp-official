"""Task runner dispatcher.

Supports two modes configured via settings:
1. USE_CELERY=True (Default/Docker): Dispatches tasks asynchronously via Celery + Redis broker.
2. USE_CELERY=False (Cloud/Render/In-Process): Dispatches tasks directly in a background thread pool without Redis or Celery.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any
from uuid import uuid4

from app.core.config import get_settings

log = logging.getLogger(__name__)

# In-process worker thread pool for cloud/serverless environments without Celery/Redis
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="inprocess_task_worker")
_local_jobs: dict[str, Any] = {}
_local_jobs_lock = Lock()


def dispatch_task(task_obj: Any, *args: Any, **kwargs: Any) -> Any:
    """Dispatches a task either via Celery (if USE_CELERY=True) or in-process thread pool (if USE_CELERY=False).

    Args:
        task_obj: The Celery task object or plain callable.
        *args: Positional arguments for the task.
        **kwargs: Keyword arguments for the task.
    """
    settings = get_settings()

    if getattr(settings, "USE_CELERY", True):
        try:
            if hasattr(task_obj, "delay"):
                return task_obj.delay(*args, **kwargs)
        except Exception as exc:
            log.warning("Celery dispatch failed (%s). Falling back to in-process execution.", exc)

    # In-process background execution
    job_id = uuid4().hex

    def _runner():
        try:
            # If task_obj is a celery task, call .run or the function itself
            fn = getattr(task_obj, "run", task_obj)
            log.info("Executing in-process background task: %s", getattr(task_obj, "name", getattr(task_obj, "__name__", str(task_obj))))
            return fn(*args, **kwargs)
        except Exception as e:
            log.exception("In-process background task failed: %s", e)

    future = _executor.submit(_runner)
    future.id = job_id
    with _local_jobs_lock:
        _local_jobs[job_id] = future
        # Keep the process-local registry bounded. The API is single-instance
        # on Render Free, and jobs do not survive a restart or spin-down.
        completed = [key for key, value in _local_jobs.items() if value.done()]
        for key in completed[:-100]:
            _local_jobs.pop(key, None)
    return future


def get_local_job_result(job_id: str):
    """Return (state, result, error), or None when the ID is not local."""
    with _local_jobs_lock:
        future = _local_jobs.get(job_id)
    if future is None:
        return None
    if not future.done():
        return "PENDING", None, None
    try:
        return "SUCCESS", future.result(), None
    except Exception as exc:
        return "FAILURE", None, str(exc)
