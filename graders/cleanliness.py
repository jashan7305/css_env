import re

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
            return 1.0

        score = float(len(removed) / len(initial))
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.0