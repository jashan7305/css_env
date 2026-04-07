from .utils import extract_css_val
import re
# this grader checks consistency of font size and line height  
def grade_font_size(html, css, tokens, state=None):
    values = extract_css_val(css, ['font-size'])
    sizes = [v.strip() for _, v in values]

    if not sizes:
        return 1.0

    valid_sizes = tokens.get("font_sizes", [])
    if not valid_sizes:
        return 0.0

    valid = sum(1 for s in sizes if s in valid_sizes)

    score = valid / len(sizes)
    return max(0.0, min(1.0, score))


def grade_line_height(html, css, tokens, state=None):
    values = extract_css_val(css, ['line-height'])
    heights = [v.strip() for _, v in values]

    if not heights:
        return 1.0

    valid_heights = tokens.get("line_heights", [])
    if not valid_heights:
        return 0.0

    valid = sum(1 for h in heights if h in valid_heights)

    score = valid / len(heights)
    return max(0.0, min(1.0, score))


def grade_typograghy_consistency(css, tokes):
    sizes = re.findall(r"font-size\s*:\s*([^;]+);", css)
    if not sizes:
        return 1.0

    unique = set(sizes)
    max_allowed = 4

    if len(unique) <= max_allowed:
        return 1.0

    score = 1 - (len(unique) - max_allowed) / 5
    return max(0.0, min(1.0, score))


def grade(html, css, tokens, state=None):
    try:
        font_score = grade_font_size(html, css, tokens, state)
        height_score = grade_line_height(html, css, tokens, state)
        consistency_score = grade_typograghy_consistency(css, tokens)

        score = float((font_score + height_score + consistency_score) / 3.0)
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.0