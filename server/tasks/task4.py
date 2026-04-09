HTML = """
<section class="landing">
    <header class="hero">
        <h1 class="hero-title">Design Systems</h1>
        <p class="hero-copy">Build interfaces that scale cleanly across screens.</p>
    </header>
    <div class="stats">
        <article class="stat">Speed</article>
        <article class="stat">Consistency</article>
        <article class="stat">Accessibility</article>
    </div>
</section>
"""

CLEAN_CSS = """
.landing {
    width: 100%;
    padding: 24px;
    margin: 16px;
}

.hero {
    width: 100%;
    margin-bottom: 24px;
}

.hero-title {
    font-size: 24px;
    line-height: 1.4;
    color: #1a6fe0;
}

.hero-copy {
    font-size: 16px;
    line-height: 1.6;
    color: #333333;
}

.stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}

.stat {
    padding: 16px;
    font-size: 18px;
    line-height: 1.4;
    color: #333333;
    background-color: #ffffff;
}

@media (max-width: 768px) {
    .stats {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        width: 100%;
    }
}

@media (max-width: 480px) {
    .stats {
        grid-template-columns: 1fr;
        width: 100%;
    }

    .hero-copy {
        font-size: 14px;
    }
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
    "missing_breakpoints": True,
    "unused_rules": True,
}

MAX_STEPS = 16
SUCCESS_THRESHOLD = 0.90
GRADER_WEIGHTS = {
    "color": 0.25,
    "spacing": 0.20,
    "typography": 0.20,
    "contrast": 0.15,
    "layout": 0.10,
    "cleanliness": 0.10,
}

TASK = {
    "name": "Responsive Landing Metrics",
    "difficulty": "medium",
    "html": HTML,
    "css": CLEAN_CSS,
    "design_tokens": TOKENS,
    "config": FLAW_CONFIG,
    "graders": ["color", "spacing", "typography", "contrast", "layout", "cleanliness"],
    "grader_weights": GRADER_WEIGHTS,
    "max_steps": MAX_STEPS,
    "success_threshold": SUCCESS_THRESHOLD,
}