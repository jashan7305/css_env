import asyncio
import json
import os
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

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a frontend engineer fixing CSS to match design tokens.
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


def log_step(step: int, action: Dict[str, Any], reward: float, done: bool, error: str = "none") -> None:
    print(
        f"[STEP] step={step} action={json.dumps(action, separators=(',', ':'))} reward={reward:.2f} done={str(done).lower()} error={error}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def build_user_prompt(step: int, html: str, css: str, tokens: Dict[str, Any], violations: Any, history: List[str]) -> str:
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

        Previous steps:
        {history_block}
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


def get_model_action(client: OpenAI, step: int, obs, history: List[str]) -> Dict[str, Any]:
    prompt = build_user_prompt(step, obs.html, obs.css, obs.tokens, obs.violations, history)
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
        rewards: List[float] = []
        steps_taken = 0
        success = False

        log_start(task=task_name, env="css_env", model=MODEL_NAME)

        try:
            result = await env.reset(task=task, seed=7)

            for step in range(1, MAX_STEPS + 1):
                if result.done:
                    break

                action_payload = get_model_action(client, step, result.observation, history)
                action = CssAction(**action_payload)

                error_val = "none"
                try:
                    result = await env.step(action)
                except Exception as exc:
                    error_val = str(exc).replace(" ", "_")
                    result = await env.step(CssAction(**default_fallback_action()))

                reward = float(result.reward or 0.0)
                rewards.append(reward)
                steps_taken = step

                history.append(f"step={step} action={action_payload} reward={reward:.2f}")
                log_step(step=step, action=action_payload, reward=reward, done=bool(result.done), error=error_val)

                if result.done:
                    success = True
                    break

            score = rewards[-1] if rewards else 0.0
            log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
        finally:
            # Keep env alive across tasks only when running all tasks.
            if TASK_NAME.lower() != "all":
                await env.close()

    if TASK_NAME.lower() == "all":
        await env.close()


if __name__ == "__main__":
    asyncio.run(main())
