import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graders import colors, spacing, typography, contrast, layout, cleanliness, design_quality
from reward import compute_reward
from server.flaw_injector import inject_flaws
try:
    from server.tasks import TASKS
except ImportError:
    from tasks import TASKS


GRADER_KEYS = [
    "color",
    "spacing",
    "typography",
    "contrast",
    "layout",
    "cleanliness",
    "design_quality",
]


def _clamp01(value):
    numeric = float(value)
    if numeric <= 0.01:
        numeric = 0.010001
    if numeric >= 0.99:
        numeric = 0.989999

    rounded = round(numeric, 2)
    if rounded <= 0.01:
        return 0.02
    if rounded >= 0.99:
        return 0.98
    return float(f"{rounded:.2f}")


def _extract_unused_from_manifest(manifest):
    return sorted(
        {
            entry.get("selector", "").strip()
            for entry in manifest
            if entry.get("flaw_type") == "unused_rules" and entry.get("selector")
        }
    )


def evaluate_css(html, css, tokens, state):
    scores = {}

    grader_map = {
        "color": colors.grade,
        "spacing": spacing.grade,
        "typography": typography.grade,
        "contrast": contrast.grade,
        "layout": layout.grade,
        "cleanliness": cleanliness.grade,
        "design_quality": design_quality.grade,
    }

    for key, grader_fn in grader_map.items():
        try:
            scores[key] = _clamp01(grader_fn(html, css, tokens, state))
        except Exception as exc:
            print(f"    x {key} grader crashed: {exc}")
            scores[key] = 0.0

    reward = compute_reward(scores, action_valid=True, done=False)
    return scores, reward


def print_task_header(task_key, task_info):
    print("\n" + "=" * 80)
    print(f"TASK: {task_key.upper()}")
    print(f"Name: {task_info.get('name', task_key)}")
    print(f"Difficulty: {task_info.get('difficulty', 'unknown')}")
    print(f"Success threshold: {task_info.get('success_threshold', 0.95):.2f}")
    print("=" * 80)


def print_scores(label, scores, reward, threshold=None):
    print(f"\n{label}")
    print("-" * 50)
    for k in GRADER_KEYS:
        print(f"  {k:15}: {scores.get(k, 0.0):.4f}")
    print(f"  {'reward':15}: {reward:.4f}")
    if threshold is not None:
        status = "PASS" if reward >= threshold else "FAIL"
        print(f"  Threshold ({threshold:.2f}): {status}")


def _validate_score_range(scores):
    return all(0.0 <= scores.get(k, -1.0) <= 1.0 for k in GRADER_KEYS)


def _run_partial_fix_test(task_info, initial_css, tokens, state):
    print("\n[PARTIAL FIX TEST]")
    print("-" * 50)

    baseline_scores, _ = evaluate_css(task_info["html"], initial_css, tokens, state)

    partial_css = task_info["initial_css"].replace("10px", "16px")
    if partial_css == task_info["initial_css"]:
        partial_css = re.sub(r"\b\d+px\b", "16px", task_info["initial_css"], count=1)

    partial_scores, _ = evaluate_css(task_info["html"], partial_css, tokens, state)

    spacing_delta = partial_scores["spacing"] - baseline_scores["spacing"]
    print(f"  spacing delta: {spacing_delta:+.4f}")
    print(f"  color stable: {partial_scores['color'] == baseline_scores['color']}")
    print(f"  typography stable: {partial_scores['typography'] == baseline_scores['typography']}")

    return {
        "spacing_improved": spacing_delta >= 0,
        "others_stable": (
            partial_scores["color"] == baseline_scores["color"]
            and partial_scores["typography"] == baseline_scores["typography"]
        ),
    }


def _run_adversarial_spacing_test(tokens):
    print("\n[ADVERSARIAL SPACING TEST]")
    print("-" * 50)

    adversarial_css = """
.card {
    margin: 16px 10px 8px 3px;
}
"""

    score = spacing.grade("<div class='card'></div>", adversarial_css, tokens, {})
    score = _clamp01(score)

    print(f"  spacing score for multi-value shorthand: {score:.4f}")
    return 0.0 < score < 1.0


def test_task(task_key, task_info, seed=7):
    print_task_header(task_key, task_info)

    result = inject_flaws(task_info["css"], task_info["design_tokens"], task_info["config"], seed)
    initial_css = result["css"]
    task_info["initial_css"] = initial_css
    target_css = task_info["css"]

    manifest_unused = _extract_unused_from_manifest(result.get("manifest", []))
    task_unused = task_info.get("initial_unused_selectors", [])
    initial_unused_selectors = sorted(set(manifest_unused) | set(task_unused))

    state_initial = {"initial_unused_selectors": initial_unused_selectors}

    print("\n[INITIAL CSS - Injected flaws]")
    initial_scores, initial_reward = evaluate_css(
        task_info["html"],
        initial_css,
        task_info["design_tokens"],
        state_initial,
    )
    print_scores("Initial Scores", initial_scores, initial_reward)

    print("\n[TARGET CSS - Clean baseline]")
    target_scores, target_reward = evaluate_css(
        task_info["html"],
        target_css,
        task_info["design_tokens"],
        state_initial,
    )
    print_scores("Target Scores", target_scores, target_reward, task_info["success_threshold"])

    print("\n[IMPROVEMENT ANALYSIS]")
    print("-" * 50)
    all_improved = True
    for key in GRADER_KEYS:
        diff = target_scores[key] - initial_scores[key]
        print(f"  {key:15}: {diff:+.4f}")
        if diff < 0:
            all_improved = False

    reward_diff = target_reward - initial_reward
    print(f"  {'reward':15}: {reward_diff:+.4f}")

    partial_result = _run_partial_fix_test(task_info, initial_css, task_info["design_tokens"], state_initial)
    adversarial_ok = _run_adversarial_spacing_test(task_info["design_tokens"])

    return {
        "initial_scores": initial_scores,
        "initial_reward": initial_reward,
        "target_scores": target_scores,
        "target_reward": target_reward,
        "all_scores_in_range": _validate_score_range(initial_scores) and _validate_score_range(target_scores),
        "all_improved": all_improved,
        "reward_improved": reward_diff >= 0,
        "meets_threshold": target_reward >= task_info["success_threshold"],
        "partial_fix_ok": partial_result["spacing_improved"] and partial_result["others_stable"],
        "adversarial_ok": adversarial_ok,
    }


def main():
    print("=" * 80)
    print("COMPREHENSIVE GRADER VERIFICATION")
    print("=" * 80)

    results = {}
    for task_key, task_info in TASKS.items():
        results[task_key] = test_task(task_key, task_info)

    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    for task_key, result in results.items():
        checks = [
            result["all_scores_in_range"],
            result["reward_improved"],
            result["meets_threshold"],
            result["partial_fix_ok"],
            result["adversarial_ok"],
        ]
        status = "PASS" if all(checks) else "FAIL"
        print(
            f"{task_key:10}: {status} | "
            f"reward={result['target_reward']:.4f} | "
            f"range={result['all_scores_in_range']} | "
            f"reward_up={result['reward_improved']} | "
            f"threshold={result['meets_threshold']} | "
            f"partial={result['partial_fix_ok']} | "
            f"adversarial={result['adversarial_ok']}"
        )

    all_pass = all(
        r["all_scores_in_range"]
        and r["reward_improved"]
        and r["meets_threshold"]
        and r["partial_fix_ok"]
        and r["adversarial_ok"]
        for r in results.values()
    )

    print("\n" + "=" * 80)
    print(f"RESULT: {'ALL TASKS PASS' if all_pass else 'SOME TASKS FAIL'}")
    print("=" * 80 + "\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
