import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graders import colors, spacing, typography, contrast, layout, cleanliness, design_quality


TOKENS = {
    "colors": {
        "primary": "#1a6fe0",
        "text": "#333333",
        "white": "#ffffff",
        "danger": "#ff6b6b",
    },
    "spacing": {"sm": 8, "md": 16, "lg": 24},
    "font_sizes": ["12px", "14px", "16px", "20px"],
    "line_heights": ["1.2", "1.4", "1.6"],
}


def _assert_mid(value: float):
    assert 0.0 < value < 1.0


def test_colors_cases():
    html = "<div class='a'></div>"
    css_good = ".a{color:#1a6fe0;background:#ffffff;}"
    css_bad = ".a{color:#123456;background:#abcdef;}"
    css_mid = ".a{color:#1a6fe0;background:#abcdef;}"

    assert colors.grade(html, css_good, TOKENS, {}) == 1.0
    assert colors.grade(html, css_bad, TOKENS, {}) == 0.0
    _assert_mid(colors.grade(html, css_mid, TOKENS, {}))


def test_spacing_cases():
    html = "<div class='a'></div>"
    css_good = ".a{margin:16px;padding:8px;gap:24px;}"
    css_bad = ".a{margin:10px;padding:14px;gap:22px;}"
    css_mid = ".a{margin:16px;padding:14px;gap:24px;}"

    assert spacing.grade(html, css_good, TOKENS, {}) == 1.0
    assert spacing.grade(html, css_bad, TOKENS, {}) == 0.0
    _assert_mid(spacing.grade(html, css_mid, TOKENS, {}))


def test_typography_cases():
    html = "<div class='a'></div>"
    css_good = ".a{font-size:16px;line-height:1.6;}"
    css_bad = ".a{font-size:15px;line-height:1.5;}"
    css_mid = ".a{font-size:16px;line-height:1.5;}"

    assert typography.grade(html, css_good, TOKENS, {}) == 1.0
    assert typography.grade(html, css_bad, TOKENS, {}) < 0.5
    _assert_mid(typography.grade(html, css_mid, TOKENS, {}))


def test_contrast_cases():
    html = "<div class='a'></div>"
    css_good = ".a{color:#000000;background-color:#ffffff;}"
    css_bad = ".a{color:#cccccc;background-color:#ffffff;}"
    css_mid = ".a{color:#000000;background-color:#ffffff;} .b{color:#cccccc;background:#ffffff;}"

    assert contrast.grade(html, css_good, TOKENS, {}) == 1.0
    assert contrast.grade(html, css_bad, TOKENS, {}) == 0.0
    _assert_mid(contrast.grade(html, css_mid, TOKENS, {}))


def test_layout_cases():
    html = "<div class='container'></div>"
    css_good = ".container{width:100%;} @media (max-width:768px){.container{display:flex;width:100%;}} @media (max-width:480px){.container{display:grid;width:100%;}}"
    css_bad = ".container{width:847px;}"
    css_mid = ".container{width:100%;} @media (max-width:768px){.container{display:flex;}}"

    assert layout.grade(html, css_good, TOKENS, {}) == 1.0
    assert layout.grade(html, css_bad, TOKENS, {}) == 0.0
    _assert_mid(layout.grade(html, css_mid, TOKENS, {}))


def test_cleanliness_cases():
    html = "<div class='card'></div>"
    state = {"initial_unused_selectors": [".unused", ".legacy"]}
    css_good = ".card{color:#333333;}"
    css_bad = ".card{color:#333333;}.unused{display:none;}.legacy{display:none;}"
    css_mid = ".card{color:#333333;}.unused{display:none;}"

    assert cleanliness.grade(html, css_good, TOKENS, state) == 1.0
    assert cleanliness.grade(html, css_bad, TOKENS, state) == 0.0
    _assert_mid(cleanliness.grade(html, css_mid, TOKENS, state))


def test_design_quality_cases():
    html = "<div class='a'></div>"
    css_good = ".a{color:#1a6fe0;font-size:16px;}"
    css_bad = (
        ".a{background:linear-gradient(red,blue);"
        "box-shadow:1px 1px #000;box-shadow:2px 2px #000;box-shadow:3px 3px #000;box-shadow:4px 4px #000;box-shadow:5px 5px #000;"
        "border-radius:9999px;border-radius:9999px;border-radius:9999px;"
        "position:absolute;position:absolute;position:absolute;position:absolute;"
        "width:10px;height:10px;width:12px;height:12px;width:14px;height:14px;width:16px;height:16px;"
        "border:1px solid #111111;border-top:1px solid #222222;border-bottom:1px solid #333333;border-left:1px solid #444444;border-right:1px solid #555555;"
        "font-size:10px;color:#111111;background-color:#eeeeee;}"
        ".b{background:linear-gradient(green,yellow);font-size:11px;color:#222222;}"
        ".c{background:linear-gradient(cyan,magenta);font-size:12px;color:#333333;}"
        ".d{font-size:13px;color:#444444;}"
        ".e{font-size:14px;color:#555555;}"
        ".f{font-size:15px;color:#666666;}"
        ".g{font-size:16px;color:#777777;}"
        ".h{font-size:17px;color:#888888;}"
        ".i{font-size:18px;color:#999999;}"
    )
    css_mid = ".a{background:linear-gradient(red,blue);color:#1a6fe0;} .b{background:linear-gradient(green,yellow);color:#333333;}"

    assert design_quality.grade(html, css_good, TOKENS, {}) == 1.0
    assert design_quality.grade(html, css_bad, TOKENS, {}) == 0.0
    _assert_mid(design_quality.grade(html, css_mid, TOKENS, {}))


if __name__ == "__main__":
    test_colors_cases()
    test_spacing_cases()
    test_typography_cases()
    test_contrast_cases()
    test_layout_cases()
    test_cleanliness_cases()
    test_design_quality_cases()
    print("All grader unit tests passed")
