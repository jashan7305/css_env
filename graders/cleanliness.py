import re
from .utils import clamp_open_unit_interval

def extract_selectors(css):
    try:
        selector_groups = re.findall(r"(?:^|\})\s*([^{}]+)\{", css)
        selectors = []
        for selector_group in selector_groups:
            for selector in selector_group.split(","):
                clean = selector.strip()
                if clean:
                    selectors.append(clean)
        return selectors
    except Exception:
        return []

def grade(html, css, tokens, state=None):
    try:
        state = state or {}
        initial = set(state.get("initial_unused_selectors", []))
        current = set(extract_selectors(css))
        removed = initial - current
        
        if not initial:
            return clamp_open_unit_interval(1.0)

        score = float(len(removed) / len(initial))
        return clamp_open_unit_interval(score)
    except Exception:
        return clamp_open_unit_interval(0.0)