# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging

import celery

logger = logging.getLogger(__name__)


def lock_key(f):
    f_path = f"{f.__module__}.{f.__name__}".replace(".", ":")
    return "discussions:lock:" + f_path


def task_is_running(
    name: str,
    exclude_task_ids: list[str] | None = None,
) -> bool:
    exclude_task_ids = exclude_task_ids or []
    workers_tasks = celery.current_app.control.inspect().active()
    if not workers_tasks:
        return False
    for tasks in workers_tasks.values():
        for task in tasks:
            if (
                task.get("name") == name
                and task.get("id") not in exclude_task_ids
            ):
                return True
    return False
