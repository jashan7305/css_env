"""
Baseline inference agent for css_env.

Uses the official OpenEnv EnvClient SDK (via the CssEnv client class
defined in client.py at project root) to drive the environment.

Reads environment variables:
  - API_BASE_URL  (default: https://api.openai.com/v1)
  - MODEL_NAME    (default: gpt-4o-mini)
  - HF_TOKEN or API_KEY or OPENAI_API_KEY (required)

Optional:
  - LOCAL_IMAGE_NAME  - Docker image name. If set, the env is launched via
                        CssEnv.from_docker_image(LOCAL_IMAGE_NAME).
  - ENV_URL           - direct base URL of an already-running css_env server
  - TASK_NAME         - task1/task2/task3/task4/easy/medium/hard/all
  - MAX_STEPS         - hard cap on loop steps per task
  - TEMPERATURE       - LLM sampling temperature
  - MAX_TOKENS        - LLM max output tokens

Emits the OpenEnv structured stdout format:
  [START] task=<task_name> env=<benchmark> model=<model_name>
  [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
  [END]   success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...,rn>
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from openai import OpenAI

from client import CssEnv
from models import CssAction

try:
    from server.tasks import TASKS, TASK_ORDER
except ImportError:
    from tasks import TASKS, TASK_ORDER


# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini").strip()
LLM_API_KEY = (
    os.getenv("HF_TOKEN")
    or os.getenv("API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or ""
).strip()

LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME", "").strip()
ENV_URL = os.getenv("ENV_URL", "http://localhost:8000").strip()
TASK_NAME = os.getenv("TASK_NAME", "all").strip()
MAX_STEPS = max(1, int(os.getenv("MAX_STEPS", "20")))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))
MAX_TOKENS = max(64, int(os.getenv("MAX_TOKENS", "350")))
BENCHMARK = "css_env"
SCORE_EPSILON = 1e-6
MIN_SCORE_BOUND = 0.01
MAX_SCORE_BOUND = 0.99

SYSTEM_PROMPT = """You are an expert frontend engineer fixing CSS to match design tokens.

Return ONLY one JSON object with this schema:
{
  "action_type": "replace_color|fix_spacing|fix_typography|fix_contrast|add_breakpoint|remove_rule",
  "target": "string",
  "value": "string or null"
}

Guidelines:
1. Prioritize the lowest score in observation.scores.
2. Do not repeat the same action signature.
3. Prefer targeted edits that change CSS and improve one dimension.
4. If a previous action had no effect, choose a different action type.
5. No markdown, no explanation, JSON only.
"""


def clamp01(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
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


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str] = None) -> None:
    done_str = "true" if done else "false"
    error_str = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_str} error={error_str}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    success_str = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={success_str} steps={steps} score={clamp01(score):.3f} rewards={rewards_str}",
        flush=True,
    )


def _task_description(task_name: str) -> str:
    cfg = TASKS.get(task_name, {})
    return str(cfg.get("description") or cfg.get("difficulty") or task_name)


def _select_tasks(task_name: str) -> List[str]:
    aliases = {"easy": "task1", "medium": "task2", "hard": "task3"}
    requested = aliases.get(task_name.lower(), task_name.lower())

    if requested == "all":
        return [name for name in TASK_ORDER if name in TASKS]
    if requested in TASKS:
        return [requested]

    known = ",".join(["all", "easy", "medium", "hard", *TASKS.keys()])
    raise ValueError(f"Unknown TASK_NAME '{task_name}'. Expected one of: {known}")


def _extract_selectors(css: str) -> List[str]:
    selectors: List[str] = []
    for selector_group in re.findall(r"([^{}]+)\{", css or ""):
        for raw in selector_group.split(","):
            selector = raw.strip()
            if selector and selector not in selectors:
                selectors.append(selector)
    return selectors


def _extract_colors(css: str) -> List[str]:
    return re.findall(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", css or "")


def _first_selector(css: str) -> str:
    selectors = _extract_selectors(css)
    return selectors[0] if selectors else ".container"


def _build_user_prompt(observation: Any, step: int, task_name: str) -> str:
    html = str(getattr(observation, "html", ""))
    css = str(getattr(observation, "css", ""))
    tokens = getattr(observation, "tokens", {}) or {}
    violations = getattr(observation, "violations", None)
    scores = getattr(observation, "scores", {}) or {}
    prev_score = getattr(observation, "score", None)

    html_preview = html[:3000]
    css_preview = css[:5000]

    return (
        f"Task: {task_name} - {_task_description(task_name)}\n"
        f"Step: {step}\n"
        f"Current score: {prev_score}\n"
        f"Scores: {json.dumps(scores, separators=(',', ':'))}\n"
        f"Violations: {json.dumps(violations)}\n"
        f"Tokens: {json.dumps(tokens, separators=(',', ':'))}\n\n"
        f"HTML:\n{html_preview}\n\n"
        f"CSS:\n{css_preview}\n"
    )


def _parse_action_json(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None

    if "```" in raw:
        lines = raw.splitlines()
        capture: List[str] = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                if in_block:
                    break
                in_block = True
                continue
            if in_block:
                capture.append(line)
        if capture:
            raw = "\n".join(capture).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None

    try:
        payload = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _fallback_action(observation: Any) -> Dict[str, Any]:
    css = str(getattr(observation, "css", ""))
    tokens = getattr(observation, "tokens", {}) or {}
    selector = _first_selector(css)

    token_colors = list((tokens.get("colors") or {}).values())
    colors = _extract_colors(css)
    if colors and token_colors:
        replacement = str(token_colors[0])
        if replacement != colors[0]:
            return {
                "action_type": "replace_color",
                "target": colors[0],
                "value": replacement,
            }

    spacing = (tokens.get("spacing") or {}).get("md", 16)
    return {
        "action_type": "fix_spacing",
        "target": f"{selector}.margin",
        "value": f"{int(spacing)}px",
    }


def _normalize_action(action: Dict[str, Any], observation: Any) -> Dict[str, Any]:
    allowed = {
        "replace_color",
        "fix_spacing",
        "fix_typography",
        "fix_contrast",
        "add_breakpoint",
        "remove_rule",
    }

    safe = dict(action or {})
    action_type = str(safe.get("action_type", "")).strip()
    if action_type not in allowed:
        return _fallback_action(observation)

    css = str(getattr(observation, "css", ""))
    selectors = _extract_selectors(css)
    first_selector = selectors[0] if selectors else ".container"

    target = str(safe.get("target", "")).strip()
    value = safe.get("value", None)

    if action_type == "replace_color":
        colors = _extract_colors(css)
        if not target or target not in colors:
            target = colors[0] if colors else "#333333"
        if value is None or not str(value).strip():
            value = "#1a6fe0"
        return {"action_type": action_type, "target": target, "value": str(value)}

    if action_type in {"fix_spacing", "fix_typography"}:
        if "." not in target:
            prop = "margin" if action_type == "fix_spacing" else "font-size"
            target = f"{first_selector}.{prop}"
        if value is None or not str(value).strip():
            value = "16px"
        return {"action_type": action_type, "target": target, "value": str(value)}

    if action_type == "fix_contrast":
        if not target:
            target = first_selector
        if value is None or "," not in str(value):
            value = "#333333,#ffffff"
        return {"action_type": action_type, "target": target, "value": str(value)}

    if action_type == "add_breakpoint":
        if not re.fullmatch(r"\d+px", target):
            target = "768px"
        if value is None or "{" not in str(value):
            value = f"{first_selector} {{ width: 100%; }}"
        return {"action_type": action_type, "target": target, "value": str(value)}

    if action_type == "remove_rule":
        if not target:
            target = selectors[-1] if selectors else ".unused"
        return {"action_type": action_type, "target": target, "value": None}

    return _fallback_action(observation)


def _action_str(action: Dict[str, Any]) -> str:
    return json.dumps(action, separators=(",", ":"), ensure_ascii=True)


def _make_openai_client() -> OpenAI:
    if not LLM_API_KEY:
        raise ValueError("Missing API key. Set HF_TOKEN or API_KEY or OPENAI_API_KEY.")
    return OpenAI(base_url=API_BASE_URL, api_key=LLM_API_KEY)


def _probe_llm(client: OpenAI) -> None:
    client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "Reply with exactly ok"},
            {"role": "user", "content": "ok"},
        ],
        temperature=0,
        max_tokens=2,
    )


async def _init_env() -> CssEnv:
    if LOCAL_IMAGE_NAME:
        return await CssEnv.from_docker_image(LOCAL_IMAGE_NAME)

    env = CssEnv(base_url=ENV_URL)
    await env.connect()
    return env


def _task_step_limit(task_cfg: Dict[str, Any]) -> int:
    task_limit = int(task_cfg.get("max_steps", MAX_STEPS) or MAX_STEPS)
    return max(1, min(task_limit, MAX_STEPS))


def _task_threshold(task_cfg: Dict[str, Any]) -> float:
    return clamp01(float(task_cfg.get("success_threshold", 0.95)))


def _llm_action(client: OpenAI, observation: Any, step: int, task_name: str) -> Dict[str, Any]:
    prompt = _build_user_prompt(observation, step, task_name)
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    text = completion.choices[0].message.content or ""
    parsed = _parse_action_json(text)
    if parsed is None:
        return _fallback_action(observation)
    return _normalize_action(parsed, observation)


async def run_task(env: CssEnv, llm_client: OpenAI, task_name: str, task_cfg: Dict[str, Any]) -> Dict[str, Any]:
    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    rewards: List[float] = []
    final_score = 0.0
    steps_taken = 0
    final_success = False

    try:
        reset_result = await env.reset(task=task_cfg, seed=7)
        observation = reset_result.observation
        done = bool(reset_result.done)
    except Exception as exc:
        log_step(step=0, action="{}", reward=0.0, done=True, error=f"reset_failed:{exc}")
        log_end(success=False, steps=0, score=0.0, rewards=[])
        return {"score": 0.0, "steps": 0, "rewards": []}

    max_steps = _task_step_limit(task_cfg)
    threshold = _task_threshold(task_cfg)

    for step in range(1, max_steps + 1):
        if done:
            break

        llm_error: Optional[str] = None
        try:
            action_payload = _llm_action(llm_client, observation, step, task_name)
        except Exception as exc:
            llm_error = f"llm_error:{exc}"
            action_payload = _fallback_action(observation)

        action_payload = _normalize_action(action_payload, observation)
        action_text = _action_str(action_payload)

        step_error: Optional[str] = llm_error
        try:
            step_result = await env.step(CssAction(**action_payload))
        except Exception as exc:
            step_error = f"step_failed:{exc}"
            action_payload = _fallback_action(observation)
            action_text = _action_str(action_payload)
            try:
                step_result = await env.step(CssAction(**action_payload))
            except Exception as exc2:
                log_step(step=step, action=action_text, reward=0.0, done=True, error=f"step_failed:{exc2}")
                steps_taken = step
                break

        reward = clamp01(float(step_result.reward or 0.0))
        done = bool(step_result.done)
        observation = step_result.observation
        rewards.append(reward)
        steps_taken = step

        observed_score = getattr(observation, "score", None)
        if observed_score is not None:
            final_score = clamp01(float(observed_score))
        elif rewards:
            final_score = clamp01(sum(rewards) / len(rewards))

        final_success = bool(getattr(observation, "success", False)) or (final_score >= threshold)
        log_step(step=step, action=action_text, reward=reward, done=done, error=step_error)

    if not rewards:
        final_score = 0.0

    log_end(success=final_success, steps=steps_taken, score=final_score, rewards=rewards)
    return {"score": final_score, "steps": steps_taken, "rewards": rewards}


async def main_async() -> None:
    try:
        tasks_to_run = _select_tasks(TASK_NAME)
    except Exception as exc:
        print(f"[DEBUG] Invalid task selection: {exc}", file=sys.stderr, flush=True)
        return

    try:
        llm_client = _make_openai_client()
        _probe_llm(llm_client)
    except Exception as exc:
        for task_name in tasks_to_run:
            log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)
            log_step(step=0, action="{}", reward=0.0, done=True, error=f"llm_init_failed:{exc}")
            log_end(success=False, steps=0, score=0.0, rewards=[])
        return

    env: Optional[CssEnv] = None
    results: Dict[str, Dict[str, Any]] = {}

    try:
        env = await _init_env()
    except Exception as exc:
        for task_name in tasks_to_run:
            log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)
            log_step(step=0, action="{}", reward=0.0, done=True, error=f"env_init_failed:{exc}")
            log_end(success=False, steps=0, score=0.0, rewards=[])
        return

    try:
        for task_name in tasks_to_run:
            task_cfg = dict(TASKS.get(task_name, {}))
            if not task_cfg:
                log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)
                log_step(step=0, action="{}", reward=0.0, done=True, error="missing_task_config")
                log_end(success=False, steps=0, score=0.0, rewards=[])
                continue

            try:
                results[task_name] = await run_task(env, llm_client, task_name, task_cfg)
            except Exception as exc:
                log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)
                log_step(step=0, action="{}", reward=0.0, done=True, error=f"task_failed:{exc}")
                log_end(success=False, steps=0, score=0.0, rewards=[])
                results[task_name] = {"score": 0.0, "steps": 0, "rewards": []}
    finally:
        if env is not None:
            try:
                await env.close()
            except Exception as exc:
                print(f"[DEBUG] env.close() error: {exc}", file=sys.stderr, flush=True)

    print("\n=== Final Results ===", file=sys.stderr)
    total = 0.0
    for task_name in tasks_to_run:
        score = clamp01(float(results.get(task_name, {}).get("score", 0.0)))
        total += score
        print(f"  {task_name}: score={score:.4f}", file=sys.stderr)
    if tasks_to_run:
        print(f"  average: {total / len(tasks_to_run):.4f}", file=sys.stderr)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
