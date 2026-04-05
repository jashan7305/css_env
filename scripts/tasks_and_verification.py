import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graders import (
    colors, spacing, typography, contrast, layout, cleanliness, design_quality
)
from reward import compute_reward

TOKENS = {
    "colors": {
        "primary": "#1a6fe0",
        "secondary": "#ff6b6b",
        "text": "#333333",
        "white": "#ffffff"
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

TASKS = {
    "easy": {
        "name": "Simple Card Component",
        "html": """
<div class="card">
    <h1 class="title">Welcome</h1>
    <p class="text">A simple card</p>
</div>
        """,
        "initial_css": """
.card {
    width: 100%;
    padding: 16px;
    margin: 8px;
}

.title {
    font-size: 20px;
    line-height: 1.4;
    color: #aabbcc;
}

.text {
    font-size: 14px;
    line-height: 1.6;
    color: #ddeeff;
}
        """,
        "target_css": """
.card {
    width: 100%;
    padding: 16px;
    margin: 8px;
}

.title {
    font-size: 20px;
    line-height: 1.4;
    color: #1a6fe0;
}

.text {
    font-size: 16px;
    line-height: 1.6;
    color: #333333;
}
        """,
        "flaws": ["mismatched colors"],
        "unused_selectors": [],
        "success_threshold": 0.70
    },
    "medium": {
        "name": "Card with Unused Styles",
        "html": """
<div class="card">
    <h1 class="title">Dashboard</h1>
    <p class="text">Overview</p>
    <button class="btn">Click</button>
</div>
        """,
        "initial_css": """
.card {
    width: auto;
    padding: 12px;
    margin: 10px;
    position: absolute;
}

.title {
    font-size: 22px;
    line-height: 1.5;
    color: #999999;
}

.text {
    font-size: 15px;
    line-height: 1.7;
    color: #666666;
}

.btn { color: red; }
.unused { color: blue; }
.old-style { display: none; }
        """,
        "target_css": """
.card {
    width: 100%;
    padding: 16px;
    margin: 16px;
}

.title {
    font-size: 20px;
    line-height: 1.4;
    color: #1a6fe0;
}

.text {
    font-size: 16px;
    line-height: 1.6;
    color: #333333;
}

.btn { color: #ff6b6b; }
        """,
        "flaws": ["mismatched colors", "wrong spacing", "unused selectors", "wrong typography", "absolute positioning"],
        "unused_selectors": [".unused", ".old-style"],
        "success_threshold": 0.65
    },
    "hard": {
        "name": "Complex Layout with Multiple Flaws",
        "html": """
<div class="container">
    <header class="header">
        <h1 class="logo">App</h1>
        <nav class="nav"></nav>
    </header>
    <main class="main">
        <section class="hero">
            <h2 class="hero-title">Welcome</h2>
            <p class="hero-text">Get started</p>
        </section>
        <section class="features">
            <div class="feature">Feature 1</div>
            <div class="feature">Feature 2</div>
        </section>
    </main>
</div>
        """,
        "initial_css": """
.container {
    width: 500px;
    padding: 13px;
    margin: 10px;
}

.header {
    width: 550px;
    display: grid;
    gap: 15px;
    position: absolute;
}

.logo {
    font-size: 28px;
    line-height: 1.3;
    color: #12ab34;
}

.nav {
    width: 25px;
    height: 25px;
}

.main {
    width: 400px;
    padding: 14px;
    margin: 12px;
}

.hero {
    background: linear-gradient(red, blue);
    width: auto;
    position: absolute;
}

.hero-title {
    font-size: 26px;
    line-height: 1.5;
    color: #aabbcc;
}

.hero-text {
    font-size: 17px;
    line-height: 1.7;
    color: #ddeeff;
}

.features {
    display: flex;
    gap: 17px;
    padding: 13px;
}

.feature {
    font-size: 18px;
    line-height: 1.3;
    color: #99aabb;
}

.old-btn { display: none; }
.disabled-section { opacity: 0; }
.deprecated { color: gray; }
.legacy-style { font-size: 11px; }
        """,
        "target_css": """
.container {
    width: 100%;
    padding: 16px;
    margin: 16px;
}

.header {
    width: 100%;
    display: grid;
    gap: 16px;
}

.logo {
    font-size: 24px;
    line-height: 1.4;
    color: #1a6fe0;
}

.nav {
    width: 100%;
}

.main {
    width: 100%;
    padding: 16px;
    margin: 16px;
}

.hero {
    width: 100%;
}

.hero-title {
    font-size: 24px;
    line-height: 1.4;
    color: #1a6fe0;
}

.hero-text {
    font-size: 16px;
    line-height: 1.6;
    color: #333333;
}

.features {
    display: flex;
    gap: 16px;
    padding: 16px;
}

.feature {
    font-size: 18px;
    line-height: 1.6;
    color: #333333;
}
        """,
        "flaws": ["wrong spacing", "mismatched colors", "unused selectors", "wrong typography", "gradients", "absolute positioning", "fixed widths"],
        "unused_selectors": [".old-btn", ".disabled-section", ".deprecated", ".legacy-style"],
        "success_threshold": 0.60
    }
}

def evaluate_css(html, css, tokens, state):
    scores = {}
    try:
        scores["color"] = colors.grade(html, css, tokens, state)
    except Exception as e:
        print(f"    ✗ Color grader crashed: {e}")
        scores["color"] = 0.0
    
    try:
        scores["spacing"] = spacing.grade(html, css, tokens, state)
    except Exception as e:
        print(f"    ✗ Spacing grader crashed: {e}")
        scores["spacing"] = 0.0
    
    try:
        scores["typography"] = typography.grade(html, css, tokens, state)
    except Exception as e:
        print(f"    ✗ Typography grader crashed: {e}")
        scores["typography"] = 0.0
    
    try:
        scores["contrast"] = contrast.grade(html, css, tokens, state)
    except Exception as e:
        print(f"    ✗ Contrast grader crashed: {e}")
        scores["contrast"] = 0.0
    
    try:
        scores["layout"] = layout.grade(html, css, tokens, state)
    except Exception as e:
        print(f"    ✗ Layout grader crashed: {e}")
        scores["layout"] = 0.0
    
    try:
        scores["cleanliness"] = cleanliness.grade(html, css, tokens, state)
    except Exception as e:
        print(f"    ✗ Cleanliness grader crashed: {e}")
        scores["cleanliness"] = 0.0
    
    try:
        scores["design_quality"] = design_quality.grade(html, css, tokens, state)
    except Exception as e:
        print(f"    ✗ Design quality grader crashed: {e}")
        scores["design_quality"] = 0.0
    
    reward = compute_reward(scores, action_valid=True, done=False)
    
    return scores, reward

def print_task_header(task_name, task_info):
    print(f"\n{'='*80}")
    print(f"TASK: {task_name.upper()}")
    print(f"Name: {task_info['name']}")
    print(f"Flaws: {', '.join(task_info['flaws'])}")
    print(f"Unused selectors: {task_info['unused_selectors']}")
    print(f"Success threshold: {task_info['success_threshold']:.2f}")
    print(f"{'='*80}")

def print_scores(label, scores, reward, threshold=None):
    print(f"\n{label}")
    print("-" * 50)
    for k, v in scores.items():
        print(f"  {k:15}: {v:.4f}")
    print(f"  {'reward':15}: {reward:.4f}")
    if threshold:
        status = "✅ PASS" if reward >= threshold else "❌ FAIL"
        print(f"  Threshold ({threshold:.2f}): {status}")

def test_task(task_name, task_info):
    print_task_header(task_name, task_info)
    
    state_initial = {"initial_unused_selectors": task_info["unused_selectors"]}
    
    print("\n[INITIAL CSS - Full of flaws]")
    initial_scores, initial_reward = evaluate_css(
        task_info["html"],
        task_info["initial_css"],
        TOKENS,
        state_initial
    )
    print_scores("Initial Scores", initial_scores, initial_reward)
    
    print("\n[TARGET CSS - Fixed and improved]")
    target_scores, target_reward = evaluate_css(
        task_info["html"],
        task_info["target_css"],
        TOKENS,
        state_initial
    )
    print_scores("Target Scores", target_scores, target_reward, task_info["success_threshold"])
    
    print("\n[IMPROVEMENT ANALYSIS]")
    print("-" * 50)
    improvements = {}
    all_improved = True
    
    for k in initial_scores.keys():
        diff = target_scores[k] - initial_scores[k]
        improvements[k] = diff
        status = "✅" if diff >= 0 else "❌"
        print(f"  {k:15}: {diff:+.4f} {status}")
        if diff < 0:
            all_improved = False
    
    reward_diff = target_reward - initial_reward
    print(f"  {'reward':15}: {reward_diff:+.4f}")
    
    print(f"\nOverall: {'✅ All graders improved' if all_improved else '❌ Some graders regressed'}")
    print(f"Reward improvement: {reward_diff:+.4f}")
    
    return {
        "initial_scores": initial_scores,
        "initial_reward": initial_reward,
        "target_scores": target_scores,
        "target_reward": target_reward,
        "improvements": improvements,
        "all_improved": all_improved,
        "meets_threshold": target_reward >= task_info["success_threshold"]
    }

def main():
    print("="*80)
    print("COMPREHENSIVE GRADER VERIFICATION & TASK DEFINITIONS")
    print("="*80)
    
    results = {}
    
    for task_name, task_info in TASKS.items():
        results[task_name] = test_task(task_name, task_info)
    
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    for task_name, result in results.items():
        status = "✅" if result["meets_threshold"] else "❌"
        print(f"\n{task_name:10}: {status} | Reward: {result['target_reward']:.4f} (threshold: {TASKS[task_name]['success_threshold']:.2f})")
    
    all_pass = all(r["meets_threshold"] for r in results.values())
    
    print("\n" + "="*80)
    print(f"RESULT: {'✅ ALL TASKS PASS' if all_pass else '❌ SOME TASKS FAIL'}")
    print("="*80 + "\n")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
