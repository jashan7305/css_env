import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graders import (
    colors, spacing, typography, contrast, layout, cleanliness, design_quality
)
from reward import compute_reward

SAMPLE_HTML = """
<div class="container">
  <h1 class="title">Hello World</h1>
  <p class="text">This is a test.</p>
</div>
"""

SAMPLE_TOKENS = {
    "colors": {
        "primary": "#FF5733",
        "secondary": "#3357FF",
        "accent": "#33FF57"
    },
    "spacing": {
        "xs": 4,
        "sm": 8,
        "md": 16,
        "lg": 24,
        "xl": 32
    },
    "font_sizes": ["12px", "14px", "16px", "18px", "20px", "24px"],
    "line_heights": ["1.2", "1.4", "1.6", "1.8"]
}

SAMPLE_CSS = """
.container {
    margin: 16px;
    padding: 16px;
    display: flex;
    gap: 8px;
}

.title {
    font-size: 24px;
    line-height: 1.4;
    color: #FF5733;
}

.text {
    font-size: 16px;
    line-height: 1.6;
    color: #3357FF;
    padding: 8px;
}
"""

TASKS = {
    "easy": {
        "html": SAMPLE_HTML,
        "css": SAMPLE_CSS,
        "tokens": SAMPLE_TOKENS,
        "state": {"initial_unused_selectors": []}
    },
    "medium": {
        "html": SAMPLE_HTML + '<div class="unused"></div>',
        "css": SAMPLE_CSS + "\n.unused { color: red; }",
        "tokens": SAMPLE_TOKENS,
        "state": {"initial_unused_selectors": [".unused"]}
    },
    "hard": {
        "html": SAMPLE_HTML,
        "css": """
.container {
    margin: 10px;
    padding: 12px;
    display: grid;
    gap: 15px;
}

.title {
    font-size: 22px;
    line-height: 1.5;
    color: #FFAA00;
}

.text {
    font-size: 15px;
    line-height: 1.7;
    color: #00AAFF;
    padding: 14px;
}

.unused { color: #999999; }
.extra { color: #777777; }
.more { border: 5px solid #123456; border: 5px solid #234567; }
""",
        "tokens": SAMPLE_TOKENS,
        "state": {"initial_unused_selectors": [".unused", ".extra", ".more"]}
    }
}

def run_tests():
    print("=" * 80)
    print("GRADER TESTS - Comprehensive Report")
    print("=" * 80)
    
    for task_name, task_data in TASKS.items():
        print(f"\n{'='*80}")
        print(f"TASK: {task_name.upper()}")
        print(f"{'='*80}")
        
        html = task_data["html"]
        css = task_data["css"]
        tokens = task_data["tokens"]
        state = task_data["state"]
        
        scores = {}
        
        # Test each grader
        try:
            score = colors.grade(html, css, tokens, state)
            scores["color"] = score
            print(f"✓ Color Grader:        {score:.4f}")
        except Exception as e:
            print(f"✗ Color Grader:        FAILED - {e}")
            scores["color"] = 0.0
        
        try:
            score = spacing.grade(html, css, tokens, state)
            scores["spacing"] = score
            print(f"✓ Spacing Grader:      {score:.4f}")
        except Exception as e:
            print(f"✗ Spacing Grader:      FAILED - {e}")
            scores["spacing"] = 0.0
        
        try:
            score = typography.grade(html, css, tokens, state)
            scores["typography"] = score
            print(f"✓ Typography Grader:   {score:.4f}")
        except Exception as e:
            print(f"✗ Typography Grader:   FAILED - {e}")
            scores["typography"] = 0.0
        
        try:
            score = contrast.grade(html, css, tokens, state)
            scores["contrast"] = score
            print(f"✓ Contrast Grader:     {score:.4f}")
        except Exception as e:
            print(f"✗ Contrast Grader:     FAILED - {e}")
            scores["contrast"] = 0.0
        
        try:
            score = layout.grade(html, css, tokens, state)
            scores["layout"] = score
            print(f"✓ Layout Grader:       {score:.4f}")
        except Exception as e:
            print(f"✗ Layout Grader:       FAILED - {e}")
            scores["layout"] = 0.0
        
        try:
            score = cleanliness.grade(html, css, tokens, state)
            scores["cleanliness"] = score
            print(f"✓ Cleanliness Grader:  {score:.4f}")
        except Exception as e:
            print(f"✗ Cleanliness Grader:  FAILED - {e}")
            scores["cleanliness"] = 0.0
        
        try:
            score = design_quality.grade(html, css, tokens, state)
            scores["design_quality"] = score
            print(f"✓ Design Quality:      {score:.4f}")
        except Exception as e:
            print(f"✗ Design Quality:      FAILED - {e}")
            scores["design_quality"] = 0.0
        
        # Compute final reward
        reward_base = compute_reward(scores, action_valid=True, done=False)
        reward_success = compute_reward(scores, action_valid=True, done=True)
        
        print(f"\n{'-'*80}")
        print(f"FINAL SCORES:")
        print(f"  Average Score:       {sum(scores.values())/len(scores):.4f}")
        print(f"  Reward (base):       {reward_base:.4f}")
        print(f"  Reward (with bonus): {reward_success:.4f}")
        print(f"  All in range [0,1]:  {all(0.0 <= v <= 1.0 for v in scores.values())}")
    
    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    run_tests()
