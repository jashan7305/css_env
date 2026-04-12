"""Server-side model exports and grading payloads."""

from importlib import util
from pathlib import Path

from pydantic import Field


_ROOT_MODELS_PATH = Path(__file__).resolve().parents[1] / "models.py"
_SPEC = util.spec_from_file_location("css_env_root_models", _ROOT_MODELS_PATH)

if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load models from {_ROOT_MODELS_PATH}")

_MODULE = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class CssAction(_MODULE.CssAction):
    """Server-local alias for shared action schema."""


class CssObservation(_MODULE.CssObservation):
    """Server-local alias for shared observation schema."""


class GradeResult(_MODULE.GradeResult):
    """Server-owned grade response model used by grading endpoints."""

    score: float = Field(..., description="Overall weighted score in [0, 1]")
