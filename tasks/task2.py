HTML = """
<form class="form">
    <label class="label" for="email">Email</label>
    <input class="input" id="email" type="email" />
    <p class="helper">We never share your email.</p>
    <button class="btn" type="submit">Submit</button>
</form>
"""

CLEAN_CSS = """
.form {
    width: 100%;
    max-width: 480px;
    padding: 16px;
    margin: 16px auto;
    background-color: #ffffff;
}

.label {
    font-size: 14px;
    line-height: 1.4;
    color: #333333;
}

.input {
    width: 100%;
    margin-top: 8px;
    padding: 8px 12px;
    font-size: 16px;
    line-height: 1.6;
    color: #333333;
    background-color: #ffffff;
    border: 1px solid #1a6fe0;
}

.helper {
    margin-top: 8px;
    font-size: 12px;
    line-height: 1.4;
    color: #333333;
}

.btn {
    margin-top: 16px;
    padding: 8px 16px;
    font-size: 14px;
    line-height: 1.4;
    color: #ffffff;
    background-color: #1a6fe0;
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
    "broken_contrast": True,
    "missing_breakpoints": False,
    "unused_rules": True,
}

MAX_STEPS = 15
SUCCESS_THRESHOLD = 0.80
GRADER_WEIGHTS = {
    "color": 0.30,
    "spacing": 0.20,
    "typography": 0.20,
    "contrast": 0.20,
    "cleanliness": 0.10,
}

TASK = {
    "name": "Card With Unused Styles",
    "difficulty": "medium",
    "html": HTML,
    "css": CLEAN_CSS,
    "design_tokens": TOKENS,
    "config": FLAW_CONFIG,
    "grader_weights": GRADER_WEIGHTS,
    "max_steps": MAX_STEPS,
    "success_threshold": SUCCESS_THRESHOLD,
}
