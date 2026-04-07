# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Css Env Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import CssAction, CssObservation
except ImportError:
    from models import CssAction, CssObservation


class CssEnv(
    EnvClient[CssAction, CssObservation, State]
):
    """
    Client for the Css Env Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with CssEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset(task={"html": "<div class='card'></div>", "css": ".card{color:#1a6fe0;}", "tokens": {}, "config": {}}, seed=7)
        ...     print(result.observation.css)
        ...
        ...     result = client.step(CssAction(action_type="replace_color", target="#1a6fe0", value="#333333"))
        ...     print(result.observation.css)

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = CssEnv.from_docker_image("css_env-env:latest")
        >>> try:
        ...     result = client.reset(task={"html": "<div class='card'></div>", "css": ".card{color:#1a6fe0;}", "tokens": {}, "config": {}}, seed=7)
        ...     result = client.step(CssAction(action_type="remove_rule", target=".unused", value=None))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: CssAction) -> Dict:
        """
        Convert CssAction to JSON payload for step message.

        Args:
            action: CssAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return {
            "action_type": action.action_type,
            "target": action.target,
            "value": action.value,
        }

    def _parse_result(self, payload: Dict) -> StepResult[CssObservation]:
        """
        Parse server response into StepResult[CssObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with CssObservation
        """
        obs_data = payload.get("observation", {})
        observation = CssObservation(
            html=obs_data.get("html", ""),
            css=obs_data.get("css", ""),
            tokens=obs_data.get("tokens", {}),
            violations=obs_data.get("violations"),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
