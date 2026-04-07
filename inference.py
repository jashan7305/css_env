import asyncio
import json
import os
import re
import textwrap
from typing import List, Dict, Any

from openai import OpenAI

from client import CssEnv
from models import CssAction
from tasks import TASKS


API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN", "")
IMAGE_NAME = os.getenv("IMAGE_NAME", "css_env-env:latest")
TASK_NAME = os.getenv("TASK_NAME", "task1")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "")
MAX_STEPS = int(os.getenv("MAX_STEPS", "20"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "250"))
SUCCESS_THRESHOLD = 0.95

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a frontend engineer fixing CSS to match design tokens.
    Optimize for score improvement across all graders, not a single metric.
    If the previous action had no effect or repeated a past action, choose a different action_type or target.
    Prioritize the lowest-scoring grader first.
    Return ONLY valid JSON with this schema:
    {
      "action_type": "replace_color|fix_spacing|fix_typography|fix_contrast|add_breakpoint|remove_rule",
      "target": "string",
      "value": "string or null"
    }
    No markdown, no prose.
    """
).strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: Dict[str, Any], reward: float, done: bool, error: str = "null") -> None:
    error_val = error if error else "null"
    print(
        f"[STEP] step={step} action={json.dumps(action, separators=(',', ':'))} reward={reward:.2f} done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def build_user_prompt(
    step: int,
    html: str,
    css: str,
    tokens: Dict[str, Any],
    violations: Any,
    scores: Dict[str, float],
    history: List[str],
) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    return textwrap.dedent(
        f"""
        Step: {step}
        HTML:
        {html}

        Current CSS:
        {css}

        Tokens:
        {json.dumps(tokens)}

        Violations:
        {json.dumps(violations)}

        Current scores:
        {json.dumps(scores, separators=(',', ':'))}

        Previous steps:
        {history_block}

        Choose an action that changes CSS and improves one of the lowest scores.
        Avoid repeating the same action_type+target+value used in recent steps.
        """
    ).strip()


def safe_action_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    action_type = payload.get("action_type", "replace_color")
    target = payload.get("target", "#000000")
    value = payload.get("value", "#000000")

    if action_type == "remove_rule":
        value = None

    return {
        "action_type": str(action_type),
        "target": str(target),
        "value": None if value is None else str(value),
    }


def default_fallback_action() -> Dict[str, Any]:
    return {
        "action_type": "fix_spacing",
        "target": ".card.margin",
        "value": "16px",
    }


def action_signature(action: Dict[str, Any]) -> str:
    value = "null" if action.get("value") is None else str(action.get("value"))
    return f"{action.get('action_type')}|{action.get('target')}|{value}"


def _score_key_for_action_type(action_type: str) -> str:
    mapping = {
        "replace_color": "color",
        "fix_spacing": "spacing",
        "fix_typography": "typography",
        "fix_contrast": "contrast",
        "add_breakpoint": "layout",
        "remove_rule": "cleanliness",
    }
    return mapping.get(action_type, "")


def _extract_hex_colors(css: str) -> List[str]:
    return re.findall(r"#(?:[0-9a-fA-F]{3}){1,2}", css)


def _candidate_actions(obs) -> List[Dict[str, Any]]:
    scores = getattr(obs, "scores", None) or {}
    tokens = getattr(obs, "tokens", {}) or {}
    css = getattr(obs, "css", "")

    candidates: List[Dict[str, Any]] = []

    if scores.get("spacing", 1.0) < 0.95:
        candidates.extend([
            {"action_type": "fix_spacing", "target": ".card.margin", "value": "16px"},
            {"action_type": "fix_spacing", "target": ".card.padding", "value": "16px"},
        ])

    if scores.get("color", 1.0) < 0.95:
        token_colors = set((tokens.get("colors") or {}).values())
        css_colors = _extract_hex_colors(css)
        replacement_order = [
            (tokens.get("colors") or {}).get("primary"),
            (tokens.get("colors") or {}).get("text"),
            "#333333",
            "#1a6fe0",
        ]
        replacement_order = [c for c in replacement_order if c]
        for src in css_colors:
            if src in token_colors:
                continue
            for dst in replacement_order:
                if src != dst:
                    candidates.append(
                        {"action_type": "replace_color", "target": src, "value": dst}
                    )

    if scores.get("typography", 1.0) < 0.95:
        candidates.extend([
            {"action_type": "fix_typography", "target": ".title.font-size", "value": "20px"},
            {"action_type": "fix_typography", "target": ".text.font-size", "value": "16px"},
            {"action_type": "fix_typography", "target": ".title.line-height", "value": "1.4"},
        ])

    if scores.get("contrast", 1.0) < 0.95:
        candidates.append(
            {"action_type": "fix_contrast", "target": ".text", "value": "#333333,#ffffff"}
        )

    if scores.get("layout", 1.0) < 0.95:
        candidates.append(
            {"action_type": "add_breakpoint", "target": "768px", "value": ".card { width: 100%; }"}
        )

    if scores.get("cleanliness", 1.0) < 0.95:
        candidates.append(
            {"action_type": "remove_rule", "target": ".unused", "value": None}
        )

    if not candidates:
        candidates.extend([
            {"action_type": "add_breakpoint", "target": "640px", "value": ".card { width: 100%; }"},
            {"action_type": "fix_typography", "target": ".text.line-height", "value": "1.6"},
            {"action_type": "remove_rule", "target": ".unused", "value": None},
            default_fallback_action(),
        ])

    return [safe_action_dict(c) for c in candidates]


def choose_non_repeating_action(obs, seen_signatures: List[str]) -> Dict[str, Any]:
    blocked = set(seen_signatures)
    scores = getattr(obs, "scores", None) or {}
    for candidate in _candidate_actions(obs):
        sig = action_signature(candidate)
        score_key = _score_key_for_action_type(candidate.get("action_type", ""))
        if score_key and scores.get(score_key, 0.0) >= SUCCESS_THRESHOLD:
            continue
        if sig not in blocked:
            return candidate

    # Last-resort deterministic rotation to avoid an exact repeated signature.
    fallback_pool = [
        {"action_type": "add_breakpoint", "target": "640px", "value": ".card { width: 100%; }"},
        {"action_type": "fix_typography", "target": ".text.line-height", "value": "1.6"},
        {"action_type": "remove_rule", "target": ".unused", "value": None},
    ]
    if scores.get("spacing", 0.0) < SUCCESS_THRESHOLD:
        fallback_pool.append(default_fallback_action())

    for candidate in [safe_action_dict(c) for c in fallback_pool]:
        if action_signature(candidate) not in blocked:
            return candidate

    return safe_action_dict(fallback_pool[0])


def should_override_action(obs, action_payload: Dict[str, Any], seen_signatures: List[str]) -> bool:
    sig = action_signature(action_payload)
    if sig in set(seen_signatures):
        return True

    scores = getattr(obs, "scores", None) or {}
    score_key = _score_key_for_action_type(action_payload.get("action_type", ""))
    if score_key and scores.get(score_key, 0.0) >= SUCCESS_THRESHOLD:
        return True

    return False


def get_model_action(client: OpenAI, step: int, obs, history: List[str]) -> Dict[str, Any]:
    scores = getattr(obs, "scores", None) or {}
    prompt = build_user_prompt(step, obs.html, obs.css, obs.tokens, obs.violations, scores, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        parsed = json.loads(text)
        return safe_action_dict(parsed)
    except Exception:
        return default_fallback_action()


async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    if TASK_NAME.lower() == "all":
        selected_tasks = list(TASKS.items())
    else:
        task_name = TASK_NAME if TASK_NAME in TASKS else "task1"
        selected_tasks = [(task_name, TASKS[task_name])]

    if ENV_BASE_URL:
        env = CssEnv(base_url=ENV_BASE_URL)
    else:
        env = await CssEnv.from_docker_image(IMAGE_NAME)

    for task_name, task in selected_tasks:
        history: List[str] = []
        recent_action_signatures: List[str] = []
        rewards: List[float] = []
        steps_taken = 0
        success = False
        score = 0.0

        log_start(task=task_name, env="css_env", model=MODEL_NAME)

        try:
            result = await env.reset(task=task, seed=7)

            for step in range(1, MAX_STEPS + 1):
                if result.done:
                    break

                action_payload = get_model_action(client, step, result.observation, history)
                if should_override_action(result.observation, action_payload, recent_action_signatures):
                    action_payload = choose_non_repeating_action(result.observation, recent_action_signatures)
                action = CssAction(**action_payload)

                error_val = "null"
                try:
                    result = await env.step(action)
                except Exception as exc:
                    error_val = str(exc)
                    action_payload = choose_non_repeating_action(result.observation, recent_action_signatures)
                    result = await env.step(CssAction(**action_payload))

                reward = float(result.reward or 0.0)
                rewards.append(reward)
                steps_taken = step
                recent_action_signatures.append(action_signature(action_payload))

                score = float(getattr(result.observation, "score", score) or score)
                score = max(0.0, min(1.0, score))

                history.append(f"step={step} action={action_payload} reward={reward:.2f}")
                log_step(step=step, action=action_payload, reward=reward, done=bool(result.done), error=error_val)

                if result.done:
                    success = bool(getattr(result.observation, "success", False))
                    break

            log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
        finally:
            # Keep env alive across tasks only when running all tasks.
            if TASK_NAME.lower() != "all":
                await env.close()

    if TASK_NAME.lower() == "all":
        await env.close()


if __name__ == "__main__":
    asyncio.run(main())
