"""Canonical task registry exposed from the server package.

This package is the preferred import location for task discovery.
It re-exports the existing root task registry to keep behavior unchanged
while making task metadata available under server.tasks for validators.
"""

from importlib import util
from pathlib import Path


_ROOT_TASKS_PATH = Path(__file__).resolve().parents[2] / "tasks.py"
_SPEC = util.spec_from_file_location("css_env_root_tasks", _ROOT_TASKS_PATH)

if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load task registry from {_ROOT_TASKS_PATH}")

_MODULE = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

TASKS = _MODULE.TASKS
TASK_CONFIGS = _MODULE.TASK_CONFIGS
TASK_ORDER = _MODULE.TASK_ORDER
TASK1 = _MODULE.TASK1
TASK2 = _MODULE.TASK2
TASK3 = _MODULE.TASK3
TASK4 = _MODULE.TASK4

__all__ = ["TASKS", "TASK_CONFIGS", "TASK_ORDER", "TASK1", "TASK2", "TASK3", "TASK4"]
