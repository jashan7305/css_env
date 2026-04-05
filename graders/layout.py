import re

def grade_fluid(html, css, tokens, state=None):
    widths = re.findall(r"width\s*:\s*([^;]+);", css)
    if not widths:
        return 1.0
    fluid = sum(1 for w in widths if any(x in w for x in ["%", "vw", "auto", "fr"]))
    return fluid / len(widths)


def grade_breakpoints(html, css, tokens, state=None):
    media = re.findall(r"@media[^{]+\{([^}]+)\}", css)
    if not media:
        return 0.0
    valid = 0
    for block in media:
        if any(prop in block for prop in ["width", "display", "flex", "grid"]):
            valid += 1
    return min(valid / 2, 1.0)


def grade(html, css, tokens, state=None):
    try:
        fluid_score = grade_fluid(html, css, tokens, state)
        breakpoint_score = grade_breakpoints(html, css, tokens, state)
        
        return float((fluid_score + breakpoint_score) / 2.0)
    except Exception:
        return 0.0