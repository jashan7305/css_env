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
from openenv.core.env_server.types import State, StepResponse

try:
    from ..models import CssAction, CssObservation
    from ..reward import compute_reward
    from ..graders import colors, spacing, typography, contrast, layout, cleanliness, design_quality
    from ..tasks import TASKS
    from .action_engine import apply_action
    from .flaw_injector import inject_flaws
except ImportError:
    from models import CssAction, CssObservation
    from reward import compute_reward
    from graders import colors, spacing, typography, contrast, layout, cleanliness, design_quality
    from tasks import TASKS
    from server.action_engine import apply_action
    from server.flaw_injector import inject_flaws


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

    def __init__(self):
        """Initialize the css_env environment."""
        self.html = "" # html string in the task
        self.css = "" # css string in the task
        self.tokens = {} # design tokens given in the task as a dict of token_name -> value
        self.config = {} # config given in the task to inject flaws
        self.manifest = [] # list of dicts describing flaws
        self.difficulty = "easy"
        self.success_threshold = 0.95
        self.step_count = 0 # current step count
        self.max_steps = 20 # maximum steps
        self.state_data = {} # tracks progress

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
            }

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
                violations=violations
            )

    def step(self, action: CssAction) -> Dict:
        """
        Execute a step in the environment by applying the action generated by the agent to the CSS.
        """

        self.css, is_changed = apply_action(self.css, action)

        scores = self._run_graders() # placeholder until graders are plugged in. arijit

        # Compute reward
        reward = compute_reward(
            scores,
            action_valid=is_changed,
            done=self._is_done(scores)
        )

        self.step_count += 1
        # arijit i dont know what is happening here with the is_done thing
        done = self._is_done(scores) or self.step_count >= self.max_steps

        obs = CssObservation(
            html=self.html,
            css=self.css,
            tokens=self.tokens,
            violations=None  # only shown at reset
        )

        info = {
            "scores": scores,
            "step_count": self.step_count,
            "changed": is_changed
        }

        self.state_data["step_count"] = self.step_count

        return StepResponse(
            observation=obs.model_dump(),
            reward=reward,
            done=done,
            info=info
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
            step_count=self.state_data.get("step_count", 0)
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
        required = [
            "color",
            "spacing",
            "typography",
            "contrast",
            "layout",
            "cleanliness",
            "design_quality",
        ]
        return all(scores.get(key, 0.0) >= 0.95 for key in required)

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
