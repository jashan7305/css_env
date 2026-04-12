from typing import Dict, Iterable, Tuple
import math

try:
    from ..models import CssAction, CssObservation
except ImportError:  # pragma: no cover
    from models import CssAction, CssObservation


SCORE_EPSILON = 1e-6
MIN_SCORE_BOUND = 0.01
MAX_SCORE_BOUND = 0.99


def _min_score(scores: Dict[str, float], required_graders: Iterable[str]) -> float:
    if not scores:
        return 0.0
    required = [str(key) for key in required_graders if key]
    if not required:
        return float(min(scores.values()))
    return float(min(scores.get(key, 0.0) for key in required))


def _clamp_open_unit_interval(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = MIN_SCORE_BOUND + SCORE_EPSILON
    if not math.isfinite(numeric):
        numeric = MIN_SCORE_BOUND + SCORE_EPSILON
    if numeric <= MIN_SCORE_BOUND:
        numeric = MIN_SCORE_BOUND + SCORE_EPSILON
    if numeric >= MAX_SCORE_BOUND:
        numeric = MAX_SCORE_BOUND - SCORE_EPSILON

    rounded = round(numeric, 2)
    if rounded <= MIN_SCORE_BOUND:
        return 0.02
    if rounded >= MAX_SCORE_BOUND:
        return 0.98
    return float(f"{rounded:.2f}")


def _grade_task_score(
    observation: CssObservation,
    action: CssAction,
    required_graders: Iterable[str],
    success_threshold: float,
) -> float:
    scores = dict(observation.scores or {})
    raw_score = (
        float(observation.score)
        if observation.score is not None
        else _min_score(scores, required_graders)
    )
    _ = success_threshold
    return float(_clamp_open_unit_interval(raw_score))


def _grade_task_result(
    observation: CssObservation,
    action: CssAction,
    required_graders: Iterable[str],
    success_threshold: float,
) -> Tuple[float, bool]:
    task_score = _grade_task_score(observation, action, required_graders, success_threshold)
    success = (
        bool(observation.success)
        if observation.success is not None
        else task_score >= float(success_threshold)
    )
    return float(task_score), bool(success)


def grade_task_easy(observation: CssObservation, action: CssAction) -> float:
    return _grade_task_score(
        observation,
        action,
        required_graders=("color", "spacing", "cleanliness"),
        success_threshold=0.95,
    )


def grade_task_medium(observation: CssObservation, action: CssAction) -> float:
    return _grade_task_score(
        observation,
        action,
        required_graders=("color", "typography", "contrast"),
        success_threshold=0.95,
    )


def grade_task_hard(observation: CssObservation, action: CssAction) -> float:
    return _grade_task_score(
        observation,
        action,
        required_graders=(
            "color",
            "spacing",
            "typography",
            "contrast",
            "layout",
            "cleanliness",
        ),
        success_threshold=0.90,
    )


def grade_task_four(observation: CssObservation, action: CssAction) -> float:
    return _grade_task_score(
        observation,
        action,
        required_graders=(
            "color",
            "spacing",
            "typography",
            "contrast",
            "layout",
            "cleanliness",
        ),
        success_threshold=0.90,
    )


def bitwise_css_easy(observation: CssObservation, action: CssAction) -> float:
    return grade_task_easy(observation, action)


def bitwise_css_medium(observation: CssObservation, action: CssAction) -> float:
    return grade_task_medium(observation, action)


def bitwise_css_hard(observation: CssObservation, action: CssAction) -> float:
    return grade_task_hard(observation, action)


def bitwise_css_task4(observation: CssObservation, action: CssAction) -> float:
    return grade_task_four(observation, action)


def grade_task_easy_result(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return _grade_task_result(
        observation,
        action,
        required_graders=("color", "spacing", "cleanliness"),
        success_threshold=0.95,
    )


def grade_task_medium_result(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return _grade_task_result(
        observation,
        action,
        required_graders=("color", "typography", "contrast"),
        success_threshold=0.95,
    )


def grade_task_hard_result(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return _grade_task_result(
        observation,
        action,
        required_graders=(
            "color",
            "spacing",
            "typography",
            "contrast",
            "layout",
            "cleanliness",
        ),
        success_threshold=0.90,
    )


def grade_task_four_result(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return _grade_task_result(
        observation,
        action,
        required_graders=(
            "color",
            "spacing",
            "typography",
            "contrast",
            "layout",
            "cleanliness",
        ),
        success_threshold=0.90,
    )


TASK_GRADERS = {
    "bitwise_css_easy": bitwise_css_easy,
    "bitwise_css_medium": bitwise_css_medium,
    "bitwise_css_hard": bitwise_css_hard,
    "bitwise_css_task4": bitwise_css_task4,
}


__all__ = [
    "TASK_GRADERS",
    "grade_task_easy",
    "grade_task_medium",
    "grade_task_hard",
    "grade_task_four",
    "grade_task_easy_result",
    "grade_task_medium_result",
    "grade_task_hard_result",
    "grade_task_four_result",
    "bitwise_css_easy",
    "bitwise_css_medium",
    "bitwise_css_hard",
    "bitwise_css_task4",
]
