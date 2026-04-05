def compute_reward(scores, action_valid=True, done=False):
    reward = (
        0.25 * scores.get("color", 0) +
        0.20 * scores.get("spacing", 0) +
        0.20 * scores.get("typography", 0) +
        0.15 * scores.get("contrast", 0) +
        0.10 * scores.get("cleanliness", 0) +
        0.10 * scores.get("design_quality", 0)
    )
    # penalty for useless actions
    if not action_valid:
        reward -= 0.05
    if done and all(v > 0.95 for v in scores.values()):
        reward += 0.50

    return float(max(0.0, min(1.5, reward)))