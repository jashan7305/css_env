from typing import Dict, Iterable, Tuple

try:
    from ..models import CssAction, CssObservation
    from ..reward import compute_reward
except ImportError:  # pragma: no cover
    from models import CssAction, CssObservation
    from reward import compute_reward


def _min_score(scores: Dict[str, float], required_graders: Iterable[str]) -> float:
    if not scores:
        return 0.0
    required = [str(key) for key in required_graders if key]
    if not required:
        return float(min(scores.values()))
    return float(min(scores.get(key, 0.0) for key in required))


def _derive_reward(observation: CssObservation, scores: Dict[str, float], done: bool) -> float:
    if observation.reward is not None:
        return float(observation.reward)

    action_valid = observation.changed if observation.changed is not None else True
    action_repeated = observation.repeated_action if observation.repeated_action is not None else False

    return float(
        compute_reward(
            scores,
            action_valid=bool(action_valid),
            done=bool(done),
            action_repeated=bool(action_repeated),
        )
    )


def _grade_task(
    observation: CssObservation,
    action: CssAction,
    required_graders: Iterable[str],
    success_threshold: float,
) -> Tuple[float, bool]:
    scores = dict(observation.scores or {})
    score = (
        float(observation.score)
        if observation.score is not None
        else _min_score(scores, required_graders)
    )
    success = (
        bool(observation.success)
        if observation.success is not None
        else score >= float(success_threshold)
    )

    reward = _derive_reward(observation, scores, success)
    return float(reward), bool(success)


def grade_task_easy(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return _grade_task(
        observation,
        action,
        required_graders=("color", "spacing", "cleanliness"),
        success_threshold=0.95,
    )


def grade_task_medium(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return _grade_task(
        observation,
        action,
        required_graders=("color", "typography", "contrast"),
        success_threshold=0.95,
    )


def grade_task_hard(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return _grade_task(
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


def bitwise_css_easy(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return grade_task_easy(observation, action)


def bitwise_css_medium(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return grade_task_medium(observation, action)


def bitwise_css_hard(observation: CssObservation, action: CssAction) -> Tuple[float, bool]:
    return grade_task_hard(observation, action)


TASK_GRADERS = {
    "bitwise_css_easy": bitwise_css_easy,
    "bitwise_css_medium": bitwise_css_medium,
    "bitwise_css_hard": bitwise_css_hard,
}


__all__ = [
    "TASK_GRADERS",
    "grade_task_easy",
    "grade_task_medium",
    "grade_task_hard",
    "bitwise_css_easy",
    "bitwise_css_medium",
    "bitwise_css_hard",
]
