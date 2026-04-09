HTML = """
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
"""

CLEAN_CSS = """
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

@media (max-width: 768px) {
    .header {
        display: flex;
        flex-direction: column;
        width: 100%;
    }

    .features {
        display: grid;
        grid-template-columns: 1fr;
        width: 100%;
    }
}

@media (max-width: 480px) {
    .main {
        width: 100%;
        padding: 8px;
    }

    .hero-title {
        font-size: 20px;
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

MAX_STEPS = 20
SUCCESS_THRESHOLD = 0.95
GRADER_WEIGHTS = {
    "color": 0.30,
    "spacing": 0.20,
    "typography": 0.20,
    "contrast": 0.20,
    "cleanliness": 0.10,
}

TASK = {
    "name": "Complex Layout With Multiple Flaws",
    "difficulty": "hard",
    "html": HTML,
    "css": CLEAN_CSS,
    "design_tokens": TOKENS,
    "config": FLAW_CONFIG,
    "graders": ["color", "spacing", "typography", "contrast", "cleanliness", "layout"],
    "grader_weights": GRADER_WEIGHTS,
    "max_steps": MAX_STEPS,
    "success_threshold": SUCCESS_THRESHOLD,
}
