# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# make sure the doc strings are correct, i have done some check the others

"""
Css Env Environment Implementation.
"""

import re
from typing import Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import CssAction, CssObservation
    from ..reward import compute_reward
    from ..graders import colors, spacing, typography, contrast, layout, cleanliness, design_quality
    from ..graders.task_graders import TASK_GRADERS
    from .tasks import TASKS
    from .action_engine import apply_action
    from .flaw_injector import inject_flaws
except ImportError:
    from models import CssAction, CssObservation
    from reward import compute_reward
    from graders import colors, spacing, typography, contrast, layout, cleanliness, design_quality
    from graders.task_graders import TASK_GRADERS
    from server.tasks import TASKS
    from server.action_engine import apply_action
    from server.flaw_injector import inject_flaws


TASK_GRADER_REGISTRY = TASK_GRADERS


class CssEnvironment(Environment):
    """
    CSS Refinement RL Environment

    This environment simulates a CSS refinement task where
    an agent iteratively modifies CSS code to improve design quality.

    Example:
    >>> env = CssEnvironment()
    >>> obs = env.reset(task, seed=42)
    >>> print(obs.html) # <div class="card">Hello</div>
    >>> print(obs.css) # .card { color: #1a73e7; }
    >>> result = env.step(CssAction(
    ...     action_type="replace_color",
    ...     target="#1a73e7",
    ...     value="#1a6fe0"
    ... ))
    >>> print(result["observation"].css) # .card { color: #1a6fe0; }
    >>> print(result["reward"]) # 0.6
    >>> print(result["done"]) # False
    """

    # Enable concurrent WebSocket sessions.
    # Set to True if your environment isolates state between instances.
    # When True, multiple WebSocket clients can connect simultaneously, each
    # getting their own environment instance (when using factory mode in app.py).
    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    HIGH_SCORE_GUARD_THRESHOLD: float = 0.90
    HIGH_SCORE_MAX_DROP: float = 0.03

    def __init__(self):
        """Initialize the css_env environment."""
        self.html = "" # html string in the task
        self.css = "" # css string in the task
        self.tokens = {} # design tokens given in the task as a dict of token_name -> value
        self.config = {} # config given in the task to inject flaws
        self.manifest = [] # list of dicts describing flaws
        self.difficulty = "easy"
        self.success_threshold = 0.95
        self.required_graders = ["color", "spacing", "typography", "contrast", "cleanliness"]
        self.step_count = 0 # current step count
        self.max_steps = 20 # maximum steps
        self.state_data = {} # tracks progress

    @staticmethod
    def _action_signature(action: CssAction) -> str:
        value = "null" if action.value is None else str(action.value)
        return f"{action.action_type}|{action.target}|{value}"

    @staticmethod
    def _action_score_key(action_type: str) -> Optional[str]:
        mapping = {
            "replace_color": "color",
            "fix_spacing": "spacing",
            "fix_typography": "typography",
            "fix_contrast": "contrast",
            "add_breakpoint": "layout",
            "remove_rule": "cleanliness",
        }
        return mapping.get(action_type)

    def _is_irrelevant_action(self, action: CssAction, scores: Dict[str, float]) -> bool:
        # In easy tasks, breakpoint tuning is usually not part of the objective.
        if self.difficulty == "easy" and action.action_type == "add_breakpoint":
            return True

        score_key = self._action_score_key(action.action_type)
        if score_key and scores.get(score_key, 0.0) >= self.success_threshold:
            return True

        return False

    def reset(self, task: Optional[Dict] = None, seed: int = 0) -> CssObservation:
            """
            task = {
                "html": str,
                "css": str,
                "design_tokens": dict,
                "config": dict,
                "difficulty": "easy" | "medium" | "hard"
            }
            """

            self.step_count = 0

            if task is None or not isinstance(task, dict) or not task:
                task = TASKS["task1"]

            self.html = task["html"]
            self.tokens = task.get("design_tokens", task.get("tokens", {}))
            self.config = task.get("config", task.get("flaw_config", {}))
            self.difficulty = task.get("difficulty", "easy")
            self.max_steps = int(task.get("max_steps", self.max_steps))
            self.success_threshold = float(task.get("success_threshold", 0.95))
            required_graders = task.get("graders", self.required_graders)
            if isinstance(required_graders, list) and required_graders:
                self.required_graders = [str(k) for k in required_graders]
            else:
                self.required_graders = ["color", "spacing", "typography", "contrast", "cleanliness"]

            clean_css = task.get("css", task.get("clean_css", ""))

            result = inject_flaws(clean_css, self.tokens, self.config, seed)

            self.css = result["css"]
            self.manifest = result["manifest"]
            initial_unused_selectors = self._compute_unused_selectors(self.css, self.html)

            if task.get("initial_unused_selectors"):
                initial_unused_selectors = sorted(
                    set(initial_unused_selectors) | set(task["initial_unused_selectors"])
                )

            self.state_data = {
                "episode_id": str(uuid4()),
                "step_count": 0,
                "initial_manifest": self.manifest,
                "initial_unused_selectors": initial_unused_selectors,
                "last_action_signature": None,
                "same_action_count": 0,
                "reward_drop_streak": 0,
                "last_scores": {},
                "last_reward": None,
                "last_done": False,
                "last_success": False,
                "last_changed": True,
                "last_no_op": False,
                "last_irrelevant": False,
                "action_counts": {},
                "required_graders": list(self.required_graders),
            }

            self.state_data["last_scores"] = self._run_graders()
            self.state_data["peak_score"] = (
                min(self.state_data["last_scores"].values())
                if self.state_data.get("last_scores")
                else 0.0
            )

            violations = None
            if self.difficulty == "easy":
                violations = task.get("violations")
                if violations is None:
                    violations = [
                        {"type": "hint", "selector": "", "message": hint}
                        for hint in result.get("hints", [])
                    ]

            return CssObservation(
                html=self.html,
                css=self.css,
                tokens=self.tokens,
                violations=violations,
                scores=self.state_data.get("last_scores", {}),
                score=min(self.state_data.get("last_scores", {}).values()) if self.state_data.get("last_scores") else 0.0,
                success=False,
                changed=True,
                no_op_action=False,
                repeated_action=False,
                terminated_by_max_steps=False,
            )

    def step(self, action: CssAction) -> CssObservation:
        """
        Execute a step in the environment by applying the action generated by the agent to the CSS.
        """
        prev_scores = dict(self.state_data.get("last_scores", {}))
        prev_reward = self.state_data.get("last_reward")
        prev_score = min(prev_scores.values()) if prev_scores else 0.0
        prev_peak_score = float(self.state_data.get("peak_score", prev_score))
        old_css = self.css
        new_css, _ = apply_action(self.css, action)
        css_changed = old_css.strip() != new_css.strip()
        action_sig = self._action_signature(action)
        repeated_action = action_sig == self.state_data.get("last_action_signature")
        same_action_count = int(self.state_data.get("same_action_count", 0)) + 1 if repeated_action else 1
        action_counts = dict(self.state_data.get("action_counts", {}))
        action_counts[action_sig] = int(action_counts.get(action_sig, 0)) + 1
        duplicate_action = action_counts[action_sig] > 1
        no_op_action = not css_changed

        self.css = new_css
        scores = self._run_graders()
        success = self._is_done(scores)
        irrelevant_action = self._is_irrelevant_action(action, prev_scores)

        # Compute reward with progress and anti-repeat penalties.
        reward = compute_reward(
            scores,
            action_valid=css_changed,
            done=success,
            action_repeated=repeated_action,
            action_duplicate=duplicate_action,
            action_irrelevant=irrelevant_action,
            previous_scores=prev_scores,
            previous_reward=prev_reward,
        )

        # FIX 1: block repeated identical actions with explicit penalty.
        if repeated_action:
            reward = max(0.0, reward - 0.05)

        # Success must be driven by grader thresholds only.
        # End the episode immediately once all required scores meet the threshold.
        if success:
            self.step_count += 1
            score = min(scores.values()) if scores else 0.0

            info = {
                "scores": scores,
                "step_count": self.step_count,
                "changed": css_changed,
                "no_op_action": no_op_action,
                "repeated_action": repeated_action,
                "same_action_count": same_action_count,
                "duplicate_action": duplicate_action,
                "irrelevant_action": irrelevant_action,
                "reward_drop_too_much": False,
                "reward_drop_streak": 0,
                "reward_drop_terminated": False,
                "repeated_action_terminated": False,
                "same_action_cap_reached": False,
                "success": True,
                "high_score_degradation": False,
                "terminated_by_max_steps": False,
                "success_threshold": self.success_threshold,
                "score": score,
            }

            self.state_data["step_count"] = self.step_count
            self.state_data["last_scores"] = scores
            self.state_data["last_reward"] = reward
            self.state_data["last_done"] = True
            self.state_data["last_success"] = True
            self.state_data["last_changed"] = css_changed
            self.state_data["last_no_op"] = no_op_action
            self.state_data["last_irrelevant"] = irrelevant_action
            self.state_data["last_action_signature"] = action_sig
            self.state_data["same_action_count"] = same_action_count
            self.state_data["reward_drop_streak"] = 0
            self.state_data["peak_score"] = max(prev_peak_score, score)
            self.state_data["action_counts"] = action_counts

            return CssObservation(
                html=self.html,
                css=self.css,
                tokens=self.tokens,
                violations=None,
                scores=scores,
                score=score,
                success=True,
                changed=css_changed,
                no_op_action=no_op_action,
                repeated_action=repeated_action,
                terminated_by_max_steps=False,
                reward=reward,
                done=True,
                metadata=info,
            )

        # Track large reward drops, but allow recovery attempts.
        reward_drop_too_much = (
            prev_reward is not None and reward < (float(prev_reward) - 0.2)
        )
        reward_drop_streak = (
            int(self.state_data.get("reward_drop_streak", 0)) + 1
            if reward_drop_too_much
            else 0
        )
        reward_drop_terminated = reward_drop_streak > 2

        # FIX 4: cap repeated identical action attempts.
        same_action_cap_reached = same_action_count > 2
        repeated_action_terminated = same_action_cap_reached

        self.step_count += 1
        done = (
            success
            or self.step_count >= self.max_steps
            or repeated_action_terminated
            or reward_drop_terminated
            or same_action_cap_reached
        )
        terminated_by_max_steps = done and not success
        score = min(scores.values()) if scores else 0.0

        high_score_degradation = (
            prev_peak_score >= self.HIGH_SCORE_GUARD_THRESHOLD
            and score < (prev_peak_score - self.HIGH_SCORE_MAX_DROP)
        )

        if high_score_degradation:
            # Keep policy from drifting after reaching a strong state.
            self.css = old_css
            scores = prev_scores
            score = prev_score
            success = self._is_done(scores)
            done = True
            reward = max(0.0, (float(prev_reward) - 0.05) if prev_reward is not None else reward)

        info = {
            "scores": scores,
            "step_count": self.step_count,
            "changed": css_changed,
            "no_op_action": no_op_action,
            "repeated_action": repeated_action,
            "same_action_count": same_action_count,
            "duplicate_action": duplicate_action,
            "irrelevant_action": irrelevant_action,
            "reward_drop_too_much": reward_drop_too_much,
            "reward_drop_streak": reward_drop_streak,
            "reward_drop_terminated": reward_drop_terminated,
            "repeated_action_terminated": repeated_action_terminated,
            "same_action_cap_reached": same_action_cap_reached,
            "success": success,
            "high_score_degradation": high_score_degradation,
            "terminated_by_max_steps": terminated_by_max_steps,
            "success_threshold": self.success_threshold,
            "score": score,
        }

        self.state_data["step_count"] = self.step_count
        self.state_data["last_scores"] = scores
        self.state_data["last_reward"] = reward
        self.state_data["last_done"] = done
        self.state_data["last_success"] = success
        self.state_data["last_changed"] = css_changed
        self.state_data["last_no_op"] = no_op_action
        self.state_data["last_irrelevant"] = irrelevant_action
        self.state_data["last_action_signature"] = action_sig
        self.state_data["same_action_count"] = same_action_count
        self.state_data["reward_drop_streak"] = reward_drop_streak
        self.state_data["peak_score"] = max(prev_peak_score, score)
        self.state_data["action_counts"] = action_counts

        return CssObservation(
            html=self.html,
            css=self.css,
            tokens=self.tokens,
            violations=None,
            scores=scores,
            score=score,
            success=success,
            changed=css_changed,
            no_op_action=no_op_action,
            repeated_action=repeated_action,
            terminated_by_max_steps=terminated_by_max_steps,
            reward=reward,
            done=done,
            metadata=info,
        )

    @property
    def state(self) -> State:
        """
        Get the current environment state.

        Returns:
            Current State with episode_id and step_count
        """
        return State(
            episode_id=self.state_data.get("episode_id"),
            step_count=self.state_data.get("step_count", 0),
            success=self.state_data.get("last_success", False),
            done=self.state_data.get("last_done", False),
            reward=self.state_data.get("last_reward") if self.state_data.get("last_reward") is not None else 0.0,
            changed=self.state_data.get("last_changed", True),
            no_op_action=self.state_data.get("last_no_op", False),
            scores=self.state_data.get("last_scores", {}),
        )
    

    def _run_graders(self) -> Dict[str, float]:
        return {
            "color": self._safe_grade(colors.grade),
            "spacing": self._safe_grade(spacing.grade),
            "typography": self._safe_grade(typography.grade),
            "contrast": self._safe_grade(contrast.grade),
            "layout": self._safe_grade(layout.grade),
            "cleanliness": self._safe_grade(cleanliness.grade),
            "design_quality": self._safe_grade(design_quality.grade),
        }

    def _is_done(self, scores: Dict[str, float]) -> bool:
        required = list(self.state_data.get("required_graders") or self.required_graders)
        if not required:
            required = ["color", "spacing", "typography", "contrast", "cleanliness"]
        return all(scores.get(key, 0.0) >= self.success_threshold for key in required)

    def _safe_grade(self, grader_fn) -> float:
        try:
            score = float(grader_fn(self.html, self.css, self.tokens, self.state_data))
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.0

    def _compute_unused_selectors(self, css: str, html: str) -> List[str]:
        selector_groups = re.findall(r"([^{}]+)\{", css)
        selectors: List[str] = []

        for group in selector_groups:
            for selector in group.split(","):
                clean = selector.strip()
                if clean and clean not in selectors:
                    selectors.append(clean)

        unused = [s for s in selectors if not self._selector_matches_html(s, html)]
        return sorted(set(unused))

    def _selector_matches_html(self, selector: str, html: str) -> bool:
        # Ignore pseudo and combinator suffixes and evaluate only the right-most simple token.
        base = re.split(r"::?|\s+|>|\+|~", selector.strip())[-1]
        if not base or base == "*":
            return True

        if base.startswith("."):
            class_name = base[1:]
            return bool(re.search(rf'class\s*=\s*["\'][^"\']*\b{re.escape(class_name)}\b', html))

        if base.startswith("#"):
            element_id = base[1:]
            return bool(re.search(rf'id\s*=\s*["\']{re.escape(element_id)}["\']', html))

        if re.match(r"^[a-zA-Z][a-zA-Z0-9-]*$", base):
            return bool(re.search(rf"<{re.escape(base)}(?:\s|>)", html))

        return False
