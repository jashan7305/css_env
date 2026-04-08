# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Css Env Environment.

This module exposes a singleton-backed OpenEnv-compatible HTTP API.
It preserves environment state across /reset, /step, and /state calls
so validation and manual curl tests observe a single live episode.
"""

from typing import Any, Dict, Optional, Tuple

try:
    from cssselect2 import compile_selector_list
except Exception:  # pragma: no cover
    compile_selector_list = None

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

try:
    from openenv.core.env_server.types import State
except Exception:  # pragma: no cover
    State = None

try:
    from ..models import CssAction, CssObservation
    from ..tasks import TASKS, TASK_ORDER
    from .css_env_environment import CssEnvironment
except ImportError:
    from models import CssAction, CssObservation
    from tasks import TASKS, TASK_ORDER
    from server.css_env_environment import CssEnvironment


class ResetRequest(BaseModel):
    seed: int = 0
    episode_id: Optional[str] = None
    task_name: Optional[str] = None
    task: Optional[Dict[str, Any]] = None


class StepRequest(BaseModel):
    action: CssAction
    timeout_s: Optional[float] = Field(default=None)
    request_id: Optional[str] = Field(default=None)


class ResetResponse(BaseModel):
    observation: CssObservation
    reward: Optional[float] = None
    done: bool = False


class StepResponse(BaseModel):
    observation: CssObservation
    reward: Optional[float] = None
    done: bool = False


class SchemaResponse(BaseModel):
    action: Dict[str, Any]
    observation: Dict[str, Any]
    state: Dict[str, Any]


class MetadataResponse(BaseModel):
    name: str
    description: str
    readme_content: str
    version: str
    author: str
    documentation_url: str


app = FastAPI(
    title="OpenEnv Environment HTTP API",
    version="1.0.0",
    description=(
        "HTTP API for the BitWise CSS OpenEnv environment. "
        "State is preserved in a singleton environment instance so reset, step, and state "
        "operate on the same episode during curl and agent runs."
    ),
)

_ENV = CssEnvironment()
_CURRENT_TASK_NAME = "task1"


def _resolve_task(request: ResetRequest) -> Tuple[str, Dict[str, Any]]:
    aliases = {
        "easy": "task1",
        "medium": "task2",
        "hard": "task3",
    }

    if request.task and isinstance(request.task, dict) and request.task:
        task_name = request.task_name or request.task.get("name") or _CURRENT_TASK_NAME
        return str(task_name), request.task

    if request.task_name:
        requested = aliases.get(request.task_name.lower(), request.task_name.lower())
        if requested == "all":
            requested = "task1"
        if requested in TASKS:
            return requested, TASKS[requested]
        raise HTTPException(status_code=400, detail=f"Unknown task_name: {request.task_name}")

    return _CURRENT_TASK_NAME, TASKS[_CURRENT_TASK_NAME]


def _selector_is_valid(selector: str) -> bool:
    selector = (selector or "").strip()
    if not selector:
        return False
    if compile_selector_list is None:
        return True
    try:
        compile_selector_list(selector)
        return True
    except Exception:
        return False


def _action_error_message(action: CssAction) -> Optional[str]:
    action_type = action.action_type
    target = (action.target or "").strip()

    if action_type in {"remove_rule", "fix_contrast"}:
        if not _selector_is_valid(target):
            return f"Malformed CSS selector: {target}"
        return None

    if action_type in {"fix_spacing", "fix_typography"}:
        if "." not in target:
            return "Malformed target: expected selector.property"
        selector, prop = target.rsplit(".", 1)
        if not selector or not prop:
            return "Malformed target: expected selector.property"
        if not _selector_is_valid(selector):
            return f"Malformed CSS selector: {selector}"
        return None

    return None


def _build_observation_error_payload(observation: CssObservation, message: str) -> CssObservation:
    metadata = dict(getattr(observation, "metadata", {}) or {})
    metadata["error"] = message
    return CssObservation(
        html=observation.html,
        css=observation.css,
        tokens=observation.tokens,
        violations=observation.violations,
        scores=observation.scores,
        score=observation.score,
        success=observation.success,
        changed=observation.changed,
        no_op_action=observation.no_op_action,
        repeated_action=observation.repeated_action,
        terminated_by_max_steps=observation.terminated_by_max_steps,
        reward=observation.reward,
        done=observation.done,
        metadata=metadata,
    )


def _current_observation() -> CssObservation:
    fallback_task = TASKS.get(_CURRENT_TASK_NAME, TASKS["task1"])
    html = _ENV.html or fallback_task.get("html", "")
    css = _ENV.css or fallback_task.get("css", "")
    tokens = _ENV.tokens or fallback_task.get("design_tokens", fallback_task.get("tokens", {}))
    scores = dict(_ENV.state_data.get("last_scores", {}) or {})
    score = min(scores.values()) if scores else 0.0
    return CssObservation(
        html=html,
        css=css,
        tokens=tokens,
        violations=None,
        scores=scores,
        score=score,
        success=bool(_ENV.state_data.get("last_success", False)),
        changed=bool(_ENV.state_data.get("last_changed", True)),
        no_op_action=bool(_ENV.state_data.get("last_no_op", False)),
        repeated_action=False,
        terminated_by_max_steps=False,
        reward=_ENV.state_data.get("last_reward") if _ENV.state_data.get("last_reward") is not None else 0.0,
        done=bool(_ENV.state_data.get("last_done", False)),
        metadata={"error": "Environment error"},
    )


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "css_env"}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>BitWise CSS Env</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f8f9fb;
            --panel: #ffffff;
            --text: #1f2a37;
            --muted: #556274;
            --accent: #0f62fe;
            --border: #d6dde8;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Segoe UI, Tahoma, Geneva, Verdana, sans-serif;
            background: radial-gradient(circle at 10% 10%, #e8f0ff 0%, var(--bg) 45%);
            color: var(--text);
        }
        main {
            max-width: 900px;
            margin: 32px auto;
            padding: 0 16px;
        }
        .card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 14px;
            box-shadow: 0 8px 24px rgba(31, 42, 55, 0.06);
        }
        h1 {
            margin: 0 0 8px;
            font-size: 28px;
        }
        h2 {
            margin-top: 0;
            font-size: 18px;
        }
        p {
            margin: 8px 0;
            color: var(--muted);
            line-height: 1.45;
        }
        ul {
            margin: 8px 0 0;
            padding-left: 18px;
        }
        li { margin: 6px 0; }
        a {
            color: var(--accent);
            text-decoration: none;
            font-weight: 600;
        }
        a:hover { text-decoration: underline; }
        pre {
            margin: 10px 0 0;
            padding: 12px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: #f4f7fc;
            color: #13233a;
            overflow-x: auto;
            font-size: 13px;
            line-height: 1.45;
        }
        .ok {
            display: inline-block;
            background: #dff6dd;
            color: #0f5132;
            border: 1px solid #b8e2b1;
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <main>
        <section class="card">
            <span class="ok">SERVICE ONLINE</span>
            <h1>BitWise CSS Env</h1>
            <p>OpenEnv-compatible CSS environment running on FastAPI.</p>
        </section>

        <section class="card">
            <h2>Quick Links</h2>
            <ul>
                <li><a href="/health">GET /health</a></li>
                <li><a href="/docs">GET /docs (Swagger UI)</a></li>
                <li><a href="/openapi.json">GET /openapi.json</a></li>
                <li><a href="/schema">GET /schema</a></li>
            </ul>
        </section>

        <section class="card">
            <h2>Fast Smoke Tests</h2>
            <p>Run these commands against your deployed Space URL:</p>
            <pre>curl -i https://YOUR_SPACE_URL/health
curl -i -X POST https://YOUR_SPACE_URL/reset -H "Content-Type: application/json" -d '{}'
curl -i https://YOUR_SPACE_URL/state</pre>
        </section>
    </main>
</body>
</html>
"""


@app.get("/metadata", response_model=MetadataResponse)
async def endpoint_metadata() -> MetadataResponse:
    return MetadataResponse(
        name="css_env",
        description="OpenEnv-compatible CSS refinement environment for structured RL evaluation.",
        readme_content=(
            "The environment provides HTML, CSS, and design tokens to an RL agent and scores structured CSS edits "
            "with deterministic graders."
        ),
        version="0.1.0",
        author="Meta / OpenEnv",
        documentation_url="/docs",
    )


@app.get("/schema", response_model=SchemaResponse)
async def get_schemas() -> SchemaResponse:
    return SchemaResponse(
        action=CssAction.model_json_schema(),
        observation=CssObservation.model_json_schema(),
        state=State.model_json_schema() if State is not None else {},
    )


@app.post("/reset", response_model=ResetResponse)
async def reset(request: ResetRequest) -> ResetResponse:
    global _CURRENT_TASK_NAME

    task_name, task = _resolve_task(request)
    _CURRENT_TASK_NAME = task_name

    observation = _ENV.reset(task=task, seed=request.seed)
    _ENV.state_data["task_name"] = task_name
    _ENV.state_data["seed"] = request.seed

    return ResetResponse(observation=observation, reward=None, done=False)


@app.post("/step", response_model=StepResponse)
async def step(request: StepRequest) -> StepResponse:
    if not _ENV.html and not _ENV.css:
        task = TASKS.get(_CURRENT_TASK_NAME, TASKS["task1"])
        _ENV.reset(task=task, seed=0)

    validation_error = _action_error_message(request.action)

    try:
        observation = _ENV.step(request.action)
    except Exception as exc:  # pragma: no cover
        fallback_observation = _current_observation()
        return StepResponse(
            observation=_build_observation_error_payload(fallback_observation, str(exc)),
            reward=0.0,
            done=False,
        )

    if validation_error:
        observation = _build_observation_error_payload(observation, validation_error)
        observation = CssObservation(
            html=observation.html,
            css=observation.css,
            tokens=observation.tokens,
            violations=observation.violations,
            scores=observation.scores,
            score=observation.score,
            success=False,
            changed=False,
            no_op_action=True,
            repeated_action=observation.repeated_action,
            terminated_by_max_steps=False,
            reward=0.0,
            done=False,
            metadata=observation.metadata,
        )
        _ENV.state_data["last_reward"] = 0.0
        _ENV.state_data["last_done"] = False
        _ENV.state_data["last_success"] = False
        _ENV.state_data["last_changed"] = False
        _ENV.state_data["last_no_op"] = True

    if not observation.html or not observation.css:
        fallback_task = TASKS.get(_CURRENT_TASK_NAME, TASKS["task1"])
        observation = CssObservation(
            html=observation.html or _ENV.html or fallback_task.get("html", ""),
            css=observation.css or _ENV.css or fallback_task.get("css", ""),
            tokens=observation.tokens or _ENV.tokens or fallback_task.get("design_tokens", fallback_task.get("tokens", {})),
            violations=observation.violations,
            scores=observation.scores,
            score=observation.score,
            success=observation.success,
            changed=observation.changed,
            no_op_action=observation.no_op_action,
            repeated_action=observation.repeated_action,
            terminated_by_max_steps=observation.terminated_by_max_steps,
            reward=observation.reward,
            done=observation.done,
            metadata=observation.metadata,
        )

    reward = observation.reward if observation.reward is not None else 0.0
    done = bool(observation.done)
    return StepResponse(observation=observation, reward=reward, done=done)


@app.get("/state")
async def endpoint_state() -> State:
    return _ENV.state


@app.get("/ws")
async def websocket_hint() -> Dict[str, str]:
    return {"detail": "WebSocket sessions are not required for this submission; use /reset and /step over HTTP."}


def main() -> None:
    """Entry point for direct execution via uv run or python -m."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
