HTML = """
<div class="card">
    <h1 class="title">Welcome</h1>
    <p class="text">A simple card</p>
</div>
"""

CLEAN_CSS = """
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
"""

TOKENS = {
    "colors": {
        "primary": "#1a6fe0",
        "secondary": "#ff6b6b",
        "text": "#333333",
        "white": "#ffffff",
    },
    "spacing": {
        "xs": 4,
        "sm": 8,
        "md": 16,
        "lg": 24,
        "xl": 32,
    },
    "font_sizes": ["12px", "14px", "16px", "18px", "20px", "24px"],
    "line_heights": ["1.2", "1.4", "1.6", "1.8"],
}

FLAW_CONFIG = {
    "wrong_colors": True,
    "bad_spacing": True,
    "wrong_typography": True,
    "broken_contrast": False,
    "missing_breakpoints": False,
    "unused_rules": False,
}

MAX_STEPS = 10
SUCCESS_THRESHOLD = 0.95
GRADER_WEIGHTS = {
    "color": 0.30,
    "spacing": 0.20,
    "typography": 0.20,
    "contrast": 0.20,
    "cleanliness": 0.10,
}

# Easy task keeps explicit hints for training-time curriculum support.
VIOLATIONS = [
    {"type": "color", "selector": ".title"},
    {"type": "spacing", "selector": ".card"},
]

TASK = {
    "name": "Simple Card Component",
    "difficulty": "easy",
    "html": HTML,
    "css": CLEAN_CSS,
    "design_tokens": TOKENS,
    "config": FLAW_CONFIG,
    "graders": ["color", "spacing", "typography", "contrast", "cleanliness"],
    "grader_weights": GRADER_WEIGHTS,
    "max_steps": MAX_STEPS,
    "success_threshold": SUCCESS_THRESHOLD,
    "violations": VIOLATIONS,
}
