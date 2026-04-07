def compute_reward(
    scores,
    action_valid=True,
    done=False,
    action_repeated=False,
    previous_scores=None,
):
    reward = (
        0.30 * scores.get("color", 0) +
        0.20 * scores.get("spacing", 0) +
        0.20 * scores.get("typography", 0) +
        0.20 * scores.get("contrast", 0) +
        0.10 * scores.get("cleanliness", 0)
    )

    progress_bonus = 0.0
    if previous_scores:
        tracked = ["color", "spacing", "typography", "contrast", "layout", "cleanliness", "design_quality"]
        deltas = [scores.get(k, 0.0) - previous_scores.get(k, 0.0) for k in tracked]
        avg_delta = sum(deltas) / float(len(tracked))

        if avg_delta > 0:
            progress_bonus += min(0.12, avg_delta * 0.8)
        elif avg_delta < 0:
            progress_bonus += max(-0.10, avg_delta * 0.5)
        else:
            progress_bonus -= 0.02

    reward += progress_bonus

    if not action_valid:
        reward -= 0.08
    if action_repeated:
        reward -= 0.05

    if done and all(v >= 0.95 for v in scores.values()):
        reward += 0.50

    return float(max(0.0, min(1.5, reward)))