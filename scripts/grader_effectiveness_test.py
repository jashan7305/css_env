import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import copy
from graders import (
    colors, spacing, typography, contrast, layout, cleanliness, design_quality
)
from reward import compute_reward

HTML = """
<div class="card">
  <h1 class="title">Title</h1>
  <p class="text">Body</p>
</div>
"""

TOKENS = {
    "colors": {
        "primary": "#1a6fe0",
        "text": "#333333"
    },
    "spacing": {
        "sm": 8,
        "md": 16,
        "lg": 24
    },
    "font_sizes": ["14px", "16px", "20px", "24px"],
    "line_heights": ["1.4", "1.6"]
}

# ❌ BAD CSS (LLM-style messy output)
BAD_CSS = """
.card {
    margin: 10px;
    padding: 13px;
    width: 847px;
    position: absolute;
}

.title {
    font-size: 22px;
    line-height: 1.5;
    color: #123456;
}

.text {
    font-size: 15px;
    line-height: 1.7;
    color: #abcdef;
    background: linear-gradient(red, blue);
}
"""

# ✅ IMPROVED CSS (fixed)
GOOD_CSS = """
.card {
    margin: 16px;
    padding: 16px;
    width: 100%;
}

.title {
    font-size: 24px;
    line-height: 1.4;
    color: #1a6fe0;
}

.text {
    font-size: 16px;
    line-height: 1.6;
    color: #333333;
}
"""

STATE = {"initial_unused_selectors": []}


def evaluate(css):
    scores = {}

    scores["color"] = colors.grade(HTML, css, TOKENS, STATE)
    scores["spacing"] = spacing.grade(HTML, css, TOKENS, STATE)
    scores["typography"] = typography.grade(HTML, css, TOKENS, STATE)
    scores["contrast"] = contrast.grade(HTML, css, TOKENS, STATE)
    scores["layout"] = layout.grade(HTML, css, TOKENS, STATE)
    scores["cleanliness"] = cleanliness.grade(HTML, css, TOKENS, STATE)
    scores["design_quality"] = design_quality.grade(HTML, css, TOKENS, STATE)

    reward = compute_reward(scores, action_valid=True, done=False)

    return scores, reward


def print_scores(label, scores, reward):
    print(f"\n{label}")
    print("-" * 50)
    for k, v in scores.items():
        print(f"{k:15}: {v:.4f}")
    print(f"{'reward':15}: {reward:.4f}")


def compare_scores(bad_scores, good_scores):
    print("\nIMPROVEMENT CHECK")
    print("-" * 50)

    improved = True

    for key in bad_scores:
        diff = good_scores[key] - bad_scores[key]
        print(f"{key:15}: {diff:+.4f}")

        if diff < 0:
            improved = False

    print("\nOverall Improvement:", "✅ PASS" if improved else "❌ FAIL")


def run_effectiveness_test():
    print("=" * 80)
    print("GRADER EFFECTIVENESS TEST")
    print("=" * 80)

    bad_scores, bad_reward = evaluate(BAD_CSS)
    good_scores, good_reward = evaluate(GOOD_CSS)

    print_scores("BAD CSS", bad_scores, bad_reward)
    print_scores("GOOD CSS", good_scores, good_reward)

    compare_scores(bad_scores, good_scores)

    print("\nReward Improvement:", f"{good_reward - bad_reward:+.4f}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_effectiveness_test()