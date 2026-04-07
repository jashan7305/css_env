import re

def grade_fluid(html, css, tokens, state=None):
    widths = re.findall(r"(?<!max-)(?<!min-)width\s*:\s*([^;]+);", css)

    if not widths:
        return 1.0
    fluid = sum(1 for w in widths if any(x in w for x in ["%", "vw", "auto", "fr"]))
    score = fluid / len(widths)
    return max(0.0, min(1.0, score))


def grade_breakpoints(html, css, tokens, state=None):
    media_matches = re.findall(r"@media\s*\(([^\)]+)\)\s*\{([\s\S]*?)\}", css, flags=re.IGNORECASE)
    if not media_matches:
        return 0.0

    def _in_range(condition_text: str) -> bool:
        values = [int(v) for v in re.findall(r"(\d+)px", condition_text)]
        if not values:
            return False
        return any(480 <= value <= 900 for value in values)

    meaningful_rules = [
        "width",
        "display",
        "flex",
        "flex-direction",
        "grid",
        "grid-template",
    ]

    valid = 0
    for condition, block in media_matches:
        if not _in_range(condition):
            continue
        if any(prop in block for prop in meaningful_rules):
            valid += 1

    score = min(valid / 2.0, 1.0)
    return max(0.0, min(1.0, score))


def grade(html, css, tokens, state=None):
    try:
        fluid_score = grade_fluid(html, css, tokens, state)
        breakpoint_score = grade_breakpoints(html, css, tokens, state)

        score = float((fluid_score + breakpoint_score) / 2.0)
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.0