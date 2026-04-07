# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Css Env Environment.

The css_env environment is a simple test environment that echoes back messages.
"""

from openenv.core.env_server.types import Action, Observation
from pydantic import Field

from typing import Optional, Literal, Dict, List

class CssAction(Action):
    """
    Structured action for modifying CSS.
    """

    action_type: Literal[
        "replace_color",
        "fix_spacing",
        "fix_typography",
        "fix_contrast",
        "add_breakpoint",
        "remove_rule"
    ] = Field(..., description="Type of CSS transformation")

    target: str = Field(
        ...,
        description=(
            "Target of the action. Examples:\n"
            "- replace_color: old color value (e.g. '#1a73e7')\n"
            "- fix_spacing: 'selector.property' (e.g. '.card.margin')\n"
            "- fix_typography: 'selector.property'\n"
            "- fix_contrast: selector (e.g. '.text')\n"
            "- add_breakpoint: breakpoint value (e.g. '768px')\n"
            "- remove_rule: selector (e.g. '.unused-class')"
        )
    )

    value: Optional[str] = Field(
        default=None,
        description=(
            "New value for the action. Examples:\n"
            "- replace_color: new color (e.g. '#1a6fe0')\n"
            "- fix_spacing: '16px'\n"
            "- fix_typography: '18px'\n"
            "- fix_contrast: 'fg_color,bg_color'\n"
            "- add_breakpoint: CSS rule block\n"
            "- remove_rule: None"
        )
    )


class CssObservation(Observation):
    """
    Observation returned to the agent.
    """

    html: str = Field(..., description="HTML of the component")

    css: str = Field(..., description="Current CSS stylesheet")

    tokens: Dict = Field(
        ...,
        description="Design system tokens (colors, spacing, typography, breakpoints)"
    )

    violations: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="List of violations (only present in easy task)"
    )