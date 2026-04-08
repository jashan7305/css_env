from .task1 import TASK as TASK1
from .task2 import TASK as TASK2
from .task3 import TASK as TASK3
from .task4 import TASK as TASK4

TASKS = {
    "task1": TASK1,
    "task2": TASK2,
    "task3": TASK3,
    "task4": TASK4,
}

TASK_CONFIGS = TASKS
TASK_ORDER = ["task1", "task2", "task3", "task4"]

__all__ = ["TASKS", "TASK_CONFIGS", "TASK_ORDER", "TASK1", "TASK2", "TASK3", "TASK4"]
