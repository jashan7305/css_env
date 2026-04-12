"""Canonical task registry exposed from the server package.

Task content comes from the root ``tasks.py`` module, while grader discovery
metadata (notably ``grader_weights``) is sourced from JSON files in this
directory (``task*.json``).
"""

from copy import deepcopy
from importlib import util
import json
from pathlib import Path
from typing import Any, Dict, List


_TASKS_DIR = Path(__file__).resolve().parent
_ROOT_TASKS_PATH = Path(__file__).resolve().parents[2] / "tasks.py"
_SPEC = util.spec_from_file_location("css_env_root_tasks", _ROOT_TASKS_PATH)

if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load task registry from {_ROOT_TASKS_PATH}")

_MODULE = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _normalize_grader_weights(raw_weights: Any) -> Dict[str, float]:
    if not isinstance(raw_weights, dict):
        return {}

    normalized: Dict[str, float] = {}
    for grader_key, weight in raw_weights.items():
        key = str(grader_key).strip()
        if not key:
            continue
        try:
            normalized[key] = float(weight)
        except (TypeError, ValueError):
            continue
    return normalized


def _normalize_graders(raw_graders: Any) -> List[str]:
    if not isinstance(raw_graders, list):
        return []
    return [str(grad).strip() for grad in raw_graders if str(grad).strip()]


def _load_task_json_configs() -> Dict[str, Dict[str, Any]]:
    configs: Dict[str, Dict[str, Any]] = {}

    for config_path in sorted(_TASKS_DIR.glob("task*.json")):
        try:
            parsed = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(parsed, dict):
            continue

        task_id = str(parsed.get("id") or config_path.stem).strip().lower()
        if not task_id:
            continue

        parsed["id"] = task_id
        parsed["grader_weights"] = _normalize_grader_weights(parsed.get("grader_weights"))
        parsed["graders"] = (
            _normalize_graders(parsed.get("graders"))
            or [k for k, v in parsed["grader_weights"].items() if v > 0.0]
        )

        configs[task_id] = parsed

    return configs


def _merge_task(base_task: Dict[str, Any], task_config: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base_task)

    for key, value in task_config.items():
        if key == "id":
            continue
        merged[key] = deepcopy(value)

    merged["grader_weights"] = _normalize_grader_weights(merged.get("grader_weights"))
    merged["graders"] = (
        _normalize_graders(merged.get("graders"))
        or [k for k, v in merged["grader_weights"].items() if v > 0.0]
    )

    return merged


_ROOT_TASKS: Dict[str, Dict[str, Any]] = dict(_MODULE.TASKS)
TASK_JSON_CONFIGS = _load_task_json_configs()

TASKS: Dict[str, Dict[str, Any]] = {}
for task_id, root_task in _ROOT_TASKS.items():
    merged = _merge_task(dict(root_task), TASK_JSON_CONFIGS.get(task_id, {}))
    TASKS[task_id] = merged

for task_id, task_config in TASK_JSON_CONFIGS.items():
    if task_id in TASKS:
        continue
    TASKS[task_id] = _merge_task({}, task_config)


_root_order = list(getattr(_MODULE, "TASK_ORDER", []))
TASK_ORDER = [task_id for task_id in _root_order if task_id in TASKS]
for task_id in sorted(TASKS.keys()):
    if task_id not in TASK_ORDER:
        TASK_ORDER.append(task_id)

TASK_CONFIGS = TASK_JSON_CONFIGS

TASK1 = TASKS.get("task1", {})
TASK2 = TASKS.get("task2", {})
TASK3 = TASKS.get("task3", {})
TASK4 = TASKS.get("task4", {})

__all__ = [
    "TASKS",
    "TASK_CONFIGS",
    "TASK_JSON_CONFIGS",
    "TASK_ORDER",
    "TASK1",
    "TASK2",
    "TASK3",
    "TASK4",
]
