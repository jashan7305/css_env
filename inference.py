import asyncio
import json
import os
import re
import textwrap
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import OpenAI

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from client import CssEnv
from models import CssAction
from tasks import TASK_CONFIGS, TASK_ORDER


API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN", "")
IMAGE_NAME = os.getenv("IMAGE_NAME", "css_env-env:latest")
TASK_NAME = os.getenv("TASK_NAME", "task1")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "")
MAX_STEPS = int(os.getenv("MAX_STEPS", "20"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "250"))
DEFAULT_SUCCESS_THRESHOLD = 0.95
CURRENT_TASK_DIFFICULTY = "easy"


class _HttpCssEnv:
    """Minimal async HTTP adapter for reset/step/state endpoints."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0)

    @staticmethod
    def _parse_result(payload: Dict[str, Any]) -> Any:
        obs_data = payload.get("observation", {}) or {}
        observation = SimpleNamespace(
            html=obs_data.get("html", ""),
            css=obs_data.get("css", ""),
            tokens=obs_data.get("tokens", {}) or {},
            violations=obs_data.get("violations"),
            scores=obs_data.get("scores") or {},
            score=obs_data.get("score"),
            success=obs_data.get("success"),
            changed=obs_data.get("changed"),
            no_op_action=obs_data.get("no_op_action"),
            repeated_action=obs_data.get("repeated_action"),
            terminated_by_max_steps=obs_data.get("terminated_by_max_steps"),
            metadata=obs_data.get("metadata") or {},
        )
        return SimpleNamespace(
            observation=observation,
            reward=payload.get("reward"),
            done=bool(payload.get("done", False)),
        )

    async def reset(self, task: Optional[Dict[str, Any]] = None, seed: int = 0) -> Any:
        body: Dict[str, Any] = {"seed": seed}
        if task is not None:
            body["task"] = task
        resp = await self._client.post(f"{self.base_url}/reset", json=body)
        resp.raise_for_status()
        return self._parse_result(resp.json())

    async def step(self, action: CssAction) -> Any:
        body = {
            "action": {
                "action_type": action.action_type,
                "target": action.target,
                "value": action.value,
            }
        }
        resp = await self._client.post(f"{self.base_url}/step", json=body)
        resp.raise_for_status()
        return self._parse_result(resp.json())

    async def close(self) -> None:
        await self._client.aclose()


async def _is_env_reachable(base_url: str, timeout_s: float = 5.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def _init_env() -> Any:
    if ENV_BASE_URL:
        env = _HttpCssEnv(base_url=ENV_BASE_URL)
        return env

    docker_error = ""
    try:
        return await CssEnv.from_docker_image(IMAGE_NAME)
    except Exception as exc:
        docker_error = str(exc)

    fallbacks = [
        "http://127.0.0.1:7860",
        "http://localhost:7860",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]
    for candidate in fallbacks:
        if await _is_env_reachable(candidate):
            return _HttpCssEnv(base_url=candidate)

    raise RuntimeError(
        f"Unable to initialize environment. Docker init failed: {docker_error or 'unknown error'}"
    )

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a frontend engineer fixing CSS to match design tokens.
    Optimize for score improvement across all graders, not a single metric.
    If the previous action had no effect or repeated a past action, choose a different action_type or target.
    Do NOT repeat the same action if reward decreases.
    If a change reduces reward, try a different action type.
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


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


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


def default_fallback_action(css: str, tokens: Dict[str, Any]) -> Dict[str, Any]:
    selectors = _extract_selectors(css)
    spacing_tokens = sorted(
        {int(v) for v in (tokens.get("spacing") or {}).values() if isinstance(v, (int, float))}
    )

    if selectors and spacing_tokens:
        mid_idx = len(spacing_tokens) // 2
        return {
            "action_type": "fix_spacing",
            "target": f"{selectors[0]}.margin",
            "value": f"{spacing_tokens[mid_idx]}px",
        }

    if selectors:
        return {
            "action_type": "remove_rule",
            "target": selectors[-1],
            "value": None,
        }

    return {
        "action_type": "add_breakpoint",
        "target": "768px",
        "value": "body { width: 100%; }",
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


def _normalize_hex(color: str) -> str:
    color = str(color).strip().lower()
    if not color.startswith("#"):
        return color
    if len(color) == 4:
        return "#" + "".join(ch * 2 for ch in color[1:])
    return color


def _parse_css_blocks(css: str) -> List[Tuple[str, Dict[str, str]]]:
    blocks: List[Tuple[str, Dict[str, str]]] = []
    for selector_group, body in re.findall(r"([^{}]+)\{([^{}]+)\}", css):
        selectors = [s.strip() for s in selector_group.split(",") if s.strip() and not s.strip().startswith("@")]
        decl_map: Dict[str, str] = {}
        for declaration in body.split(";"):
            if ":" not in declaration:
                continue
            prop, val = declaration.split(":", 1)
            prop = prop.strip().lower()
            val = val.strip()
            if prop and val:
                decl_map[prop] = val
        if not decl_map:
            continue
        for selector in selectors:
            blocks.append((selector, dict(decl_map)))
    return blocks


def _extract_selectors(css: str) -> List[str]:
    selectors: List[str] = []
    for selector, _ in _parse_css_blocks(css):
        if selector not in selectors:
            selectors.append(selector)
    return selectors


def _selector_matches_html(selector: str, html: str) -> bool:
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


def _compute_unused_selectors(css: str, html: str) -> List[str]:
    selectors = _extract_selectors(css)
    unused = [selector for selector in selectors if not _selector_matches_html(selector, html)]
    return sorted(set(unused))


def _nearest_int(value: int, options: List[int]) -> int:
    return min(options, key=lambda opt: abs(opt - value))


def _first_hex(value: str) -> str:
    matches = _extract_hex_colors(value or "")
    return _normalize_hex(matches[0]) if matches else ""


def _spacing_candidates(css: str, tokens: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = _parse_css_blocks(css)
    spacing_tokens = sorted({int(v) for v in (tokens.get("spacing") or {}).values() if isinstance(v, (int, float))})
    if not spacing_tokens:
        return []

    spacing_props = {
        "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
        "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
        "gap", "row-gap", "column-gap",
    }
    px_re = re.compile(r"(\d+)px")
    candidates: List[Dict[str, Any]] = []

    for selector, decl_map in blocks:
        for prop in spacing_props:
            value = decl_map.get(prop)
            if not value or "px" not in value:
                continue

            changed = False

            def repl(match):
                nonlocal changed
                current = int(match.group(1))
                nearest = _nearest_int(current, spacing_tokens)
                if nearest != current:
                    changed = True
                return f"{nearest}px"

            new_value = px_re.sub(repl, value)
            if changed and new_value != value:
                candidates.append({
                    "action_type": "fix_spacing",
                    "target": f"{selector}.{prop}",
                    "value": new_value,
                })

    return candidates


def _typography_candidates(css: str, tokens: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = _parse_css_blocks(css)
    font_tokens = [str(v).strip() for v in (tokens.get("font_sizes") or []) if str(v).strip()]
    line_tokens = [str(v).strip() for v in (tokens.get("line_heights") or []) if str(v).strip()]
    font_px_tokens = [int(re.match(r"^(\d+)px$", token).group(1)) for token in font_tokens if re.match(r"^(\d+)px$", token)]
    line_float_tokens = [float(token) for token in line_tokens if re.match(r"^\d+(?:\.\d+)?$", token)]

    candidates: List[Dict[str, Any]] = []

    for selector, decl_map in blocks:
        font_size = decl_map.get("font-size")
        if font_size and font_size.strip() not in font_tokens:
            match = re.match(r"^(\d+)px$", font_size.strip())
            if match and font_px_tokens:
                nearest = _nearest_int(int(match.group(1)), font_px_tokens)
                candidates.append({
                    "action_type": "fix_typography",
                    "target": f"{selector}.font-size",
                    "value": f"{nearest}px",
                })

        line_height = decl_map.get("line-height")
        if line_height and line_height.strip() not in line_tokens and line_float_tokens:
            match = re.match(r"^(\d+(?:\.\d+)?)$", line_height.strip())
            if match:
                current = float(match.group(1))
                nearest = min(line_float_tokens, key=lambda opt: abs(opt - current))
                candidates.append({
                    "action_type": "fix_typography",
                    "target": f"{selector}.line-height",
                    "value": str(nearest),
                })

    return candidates


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    def to_rgb(color: str) -> Tuple[int, int, int]:
        color = _normalize_hex(color).lstrip("#")
        if len(color) == 3:
            color = "".join(ch * 2 for ch in color)
        if len(color) != 6:
            return (0, 0, 0)
        return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))

    def luminance(rgb: Tuple[int, int, int]) -> float:
        def channel(c: float) -> float:
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = rgb
        rr, gg, bb = channel(r), channel(g), channel(b)
        return 0.2126 * rr + 0.7152 * gg + 0.0722 * bb

    l1 = luminance(to_rgb(fg_hex))
    l2 = luminance(to_rgb(bg_hex))
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


def _contrast_candidates(css: str, tokens: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = _parse_css_blocks(css)
    token_colors = tokens.get("colors") or {}
    text_color = _normalize_hex(token_colors.get("text", "#333333"))
    bg_color = _normalize_hex(token_colors.get("white", "#ffffff"))

    candidates: List[Dict[str, Any]] = []
    for selector, decl_map in blocks:
        fg = _first_hex(decl_map.get("color", ""))
        if not fg:
            continue
        bg = _first_hex(decl_map.get("background-color", "")) or _first_hex(decl_map.get("background", "")) or bg_color
        if _contrast_ratio(fg, bg) < 4.5:
            candidates.append({
                "action_type": "fix_contrast",
                "target": selector,
                "value": f"{text_color},{bg_color}",
            })

    return candidates


def _color_candidates(css: str, tokens: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = _parse_css_blocks(css)
    token_colors_map = tokens.get("colors") or {}
    token_colors = {_normalize_hex(v) for v in token_colors_map.values() if v}
    if not token_colors:
        return []

    text_color = _normalize_hex(token_colors_map.get("text", "#333333"))
    white_color = _normalize_hex(token_colors_map.get("white", "#ffffff"))
    primary_color = _normalize_hex(token_colors_map.get("primary", text_color))

    usage: Dict[str, Dict[str, int]] = {}
    for _, decl_map in blocks:
        for prop, value in decl_map.items():
            if "color" not in prop and "background" not in prop and "border" not in prop:
                continue
            for found in _extract_hex_colors(value):
                normalized = _normalize_hex(found)
                if normalized in token_colors:
                    continue
                info = usage.setdefault(normalized, {"fg": 0, "bg": 0, "total": 0})
                info["total"] += 1
                if "background" in prop:
                    info["bg"] += 1
                else:
                    info["fg"] += 1

    candidates: List[Dict[str, Any]] = []
    for source, info in sorted(usage.items(), key=lambda item: item[1]["total"], reverse=True):
        replacement = white_color if info["bg"] > info["fg"] else text_color
        if replacement == source:
            replacement = primary_color if primary_color != source else white_color
        if replacement != source:
            candidates.append({
                "action_type": "replace_color",
                "target": source,
                "value": replacement,
            })

    return candidates


def _cleanliness_candidates(css: str, html: str) -> List[Dict[str, Any]]:
    return [
        {"action_type": "remove_rule", "target": selector, "value": None}
        for selector in _compute_unused_selectors(css, html)
    ]


def _layout_candidates(css: str) -> List[Dict[str, Any]]:
    if "@media" in css or CURRENT_TASK_DIFFICULTY == "easy":
        return []
    selectors = _extract_selectors(css)
    preferred = [".container", ".main", ".card", ".form", ".header"]
    selected = next((selector for selector in preferred if selector in selectors), None)
    if selected is None:
        selected = next((selector for selector in selectors if selector.startswith(".")), ".container")
    return [{
        "action_type": "add_breakpoint",
        "target": "768px",
        "value": f"{selected} {{ width: 100%; }}",
    }]


def _dedupe_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set = set()
    for action in actions:
        safe = safe_action_dict(action)
        sig = action_signature(safe)
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(safe)
    return deduped


def _action_target_exists(obs, action_payload: Dict[str, Any]) -> bool:
    css = getattr(obs, "css", "")
    selectors = set(_extract_selectors(css))
    action_type = action_payload.get("action_type", "")
    target = str(action_payload.get("target", ""))

    if action_type == "replace_color":
        normalized_target = _normalize_hex(target)
        css_colors = {_normalize_hex(color) for color in _extract_hex_colors(css)}
        return normalized_target in css_colors
    if action_type == "remove_rule":
        return target in selectors
    if action_type in {"fix_spacing", "fix_typography"}:
        if "." not in target:
            return False
        selector, _ = target.rsplit(".", 1)
        return selector in selectors
    if action_type == "fix_contrast":
        return target in selectors
    if action_type == "add_breakpoint":
        return True
    return False


def _action_payload_is_well_formed(action_payload: Dict[str, Any]) -> bool:
    action_type = str(action_payload.get("action_type", ""))
    target = str(action_payload.get("target", "")).strip()
    value = action_payload.get("value")

    if action_type == "replace_color":
        return bool(re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", target)) and isinstance(value, str)
    if action_type in {"fix_spacing", "fix_typography"}:
        return "." in target and isinstance(value, str) and bool(value.strip())
    if action_type == "fix_contrast":
        return isinstance(value, str) and "," in value
    if action_type == "add_breakpoint":
        return bool(re.fullmatch(r"\d+px", target)) and isinstance(value, str) and "{" in value and "}" in value
    if action_type == "remove_rule":
        return bool(target)
    return False


def _action_matches_candidates(obs, action_payload: Dict[str, Any], success_threshold: float) -> bool:
    candidates = _candidate_actions(obs, success_threshold)
    if not candidates:
        return True
    sig = action_signature(safe_action_dict(action_payload))
    candidate_sigs = {action_signature(candidate) for candidate in candidates}
    return sig in candidate_sigs


def _candidate_actions(obs, success_threshold: float) -> List[Dict[str, Any]]:
    scores = getattr(obs, "scores", None) or {}
    tokens = getattr(obs, "tokens", {}) or {}
    css = getattr(obs, "css", "")
    html = getattr(obs, "html", "")

    metric_generators = {
        "spacing": lambda: _spacing_candidates(css, tokens),
        "color": lambda: _color_candidates(css, tokens),
        "typography": lambda: _typography_candidates(css, tokens),
        "contrast": lambda: _contrast_candidates(css, tokens),
        "cleanliness": lambda: _cleanliness_candidates(css, html),
        "layout": lambda: _layout_candidates(css),
    }

    candidates: List[Dict[str, Any]] = []

    ordered_metrics = [
        metric
        for metric, metric_score in sorted(scores.items(), key=lambda kv: kv[1])
        if metric in metric_generators and metric_score < success_threshold
    ]

    for metric in ordered_metrics:
        candidates.extend(metric_generators[metric]())

    if not candidates:
        for metric in ["cleanliness", "spacing", "typography", "contrast", "color", "layout"]:
            candidates.extend(metric_generators[metric]())

    if not candidates:
        candidates = [default_fallback_action(css, tokens)]

    return _dedupe_actions(candidates)


def choose_non_repeating_action(
    obs,
    seen_signatures: List[str],
    success_threshold: float,
    avoid_action_type: str = "",
) -> Dict[str, Any]:
    blocked = set(seen_signatures)
    scores = getattr(obs, "scores", None) or {}
    for candidate in _candidate_actions(obs, success_threshold):
        sig = action_signature(candidate)
        if avoid_action_type and candidate.get("action_type") == avoid_action_type:
            continue
        score_key = _score_key_for_action_type(candidate.get("action_type", ""))
        if score_key and scores.get(score_key, 0.0) >= success_threshold:
            continue
        if sig not in blocked:
            return candidate

    fallback_pool = _candidate_actions(obs, success_threshold)
    if not fallback_pool:
        fallback_pool = [default_fallback_action(getattr(obs, "css", ""), getattr(obs, "tokens", {}) or {})]

    for candidate in [safe_action_dict(c) for c in fallback_pool]:
        if avoid_action_type and candidate.get("action_type") == avoid_action_type:
            continue
        if action_signature(candidate) not in blocked:
            return candidate

    usage_counts: Dict[str, int] = {}
    for seen_sig in seen_signatures:
        usage_counts[seen_sig] = usage_counts.get(seen_sig, 0) + 1

    ranked = sorted(
        [safe_action_dict(candidate) for candidate in fallback_pool],
        key=lambda candidate: usage_counts.get(action_signature(candidate), 0),
    )
    return ranked[0]


def should_override_action(
    obs,
    action_payload: Dict[str, Any],
    seen_signatures: List[str],
    success_threshold: float,
    reward_decreased: bool = False,
    last_action_type: str = "",
) -> bool:
    if CURRENT_TASK_DIFFICULTY == "easy" and action_payload.get("action_type") == "add_breakpoint":
        return True

    if reward_decreased and last_action_type and action_payload.get("action_type") == last_action_type:
        return True

    if not _action_payload_is_well_formed(action_payload):
        return True

    if not _action_target_exists(obs, action_payload):
        return True

    if not _action_matches_candidates(obs, action_payload, success_threshold):
        return True

    sig = action_signature(action_payload)
    if sig in set(seen_signatures):
        return True

    scores = getattr(obs, "scores", None) or {}
    score_key = _score_key_for_action_type(action_payload.get("action_type", ""))
    if score_key and scores.get(score_key, 0.0) >= success_threshold:
        return True

    return False


def get_model_action(client: OpenAI, step: int, obs, history: List[str]) -> Optional[Dict[str, Any]]:
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
        return None


def select_tasks(task_name_value: str) -> List[Tuple[str, Dict[str, Any]]]:
    requested = task_name_value.lower()
    aliases = {
        "easy": "task1",
        "medium": "task2",
        "hard": "task3",
    }
    requested = aliases.get(requested, requested)
    if requested == "all":
        return [(name, TASK_CONFIGS[name]) for name in TASK_ORDER if name in TASK_CONFIGS]
    if requested in TASK_CONFIGS:
        return [(requested, TASK_CONFIGS[requested])]
    raise ValueError(f"Unknown TASK_NAME: {task_name_value}. Expected one of: {','.join(TASK_CONFIGS.keys())},all")


async def run_task(
    env: CssEnv,
    llm_client: OpenAI,
    task_name: str,
    task_config: Dict[str, Any],
) -> None:
    global CURRENT_TASK_DIFFICULTY

    CURRENT_TASK_DIFFICULTY = str(task_config.get("difficulty", "easy")).lower()
    success_threshold = clamp01(float(task_config.get("success_threshold", DEFAULT_SUCCESS_THRESHOLD)))
    max_steps_for_task = int(task_config.get("max_steps", MAX_STEPS))
    max_steps_for_task = max(1, min(max_steps_for_task, MAX_STEPS))

    history: List[str] = []
    recent_action_signatures: List[str] = []
    rewards: List[float] = []
    prev_reward = 0.0
    last_action_type = ""
    steps_taken = 0
    success = False
    score = 0.0

    log_start(task=task_name, env="css_env", model=MODEL_NAME)
    try:
        result = await env.reset(task=task_config, seed=7)
    except Exception as exc:
        log_step(step=0, action={"action_type": "reset", "target": "", "value": None}, reward=0.0, done=True, error=f"reset_failed:{exc}")
        log_end(success=False, steps=0, score=0.0, rewards=[])
        return

    try:
        for step in range(1, max_steps_for_task + 1):
            action_payload = get_model_action(llm_client, step, result.observation, history)
            if action_payload is None:
                action_payload = choose_non_repeating_action(
                    result.observation,
                    recent_action_signatures,
                    success_threshold=success_threshold,
                    avoid_action_type=last_action_type,
                )

            reward_decreased = bool(rewards) and (rewards[-1] < prev_reward)
            if should_override_action(
                result.observation,
                action_payload,
                recent_action_signatures,
                success_threshold=success_threshold,
                reward_decreased=reward_decreased,
                last_action_type=last_action_type,
            ):
                action_payload = choose_non_repeating_action(
                    result.observation,
                    recent_action_signatures,
                    success_threshold=success_threshold,
                    avoid_action_type=last_action_type if reward_decreased else "",
                )

            error_val = "null"
            try:
                result = await env.step(CssAction(**action_payload))
            except Exception as exc:
                error_val = str(exc)
                try:
                    action_payload = choose_non_repeating_action(
                        result.observation,
                        recent_action_signatures,
                        success_threshold=success_threshold,
                    )
                    result = await env.step(CssAction(**action_payload))
                except Exception as exc2:
                    log_step(step=step, action=action_payload, reward=0.0, done=True, error=f"step_failed:{exc2}")
                    break

            reward = clamp01(float(result.reward or 0.0))
            done = bool(getattr(result, "done", False))
            success = bool(getattr(result.observation, "success", False))
            if not success and done:
                success = reward >= success_threshold

            rewards.append(reward)
            prev_reward = rewards[-2] if len(rewards) >= 2 else reward
            steps_taken = step
            recent_action_signatures.append(action_signature(action_payload))
            last_action_type = str(action_payload.get("action_type", ""))
            score = clamp01(float(getattr(result.observation, "score", score) or score))

            history.append(f"step={step} action={action_payload} reward={reward:.2f}")
            log_step(step=step, action=action_payload, reward=reward, done=done, error=error_val)

            if done:
                break
    except Exception as exc:
        log_step(step=max(steps_taken, 0), action={"action_type": "internal_error", "target": "", "value": None}, reward=0.0, done=True, error=str(exc))
    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


async def main() -> None:
    llm_client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    selected_tasks = select_tasks(TASK_NAME)

    env: Optional[Any] = None
    try:
        env = await _init_env()
    except Exception as exc:
        for task_name, _ in selected_tasks:
            log_start(task=task_name, env="css_env", model=MODEL_NAME)
            log_step(step=0, action={"action_type": "init", "target": "", "value": None}, reward=0.0, done=True, error=f"env_init_failed:{exc}")
            log_end(success=False, steps=0, score=0.0, rewards=[])
        return

    try:
        for task_name, task_config in selected_tasks:
            try:
                await run_task(
                    env=env,
                    llm_client=llm_client,
                    task_name=task_name,
                    task_config=task_config,
                )
            except Exception as exc:
                log_start(task=task_name, env="css_env", model=MODEL_NAME)
                log_step(step=0, action={"action_type": "task", "target": task_name, "value": None}, reward=0.0, done=True, error=f"task_failed:{exc}")
                log_end(success=False, steps=0, score=0.0, rewards=[])
    finally:
        if env is not None:
            await env.close()


if __name__ == "__main__":
    asyncio.run(main())
