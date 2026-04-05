import re

def extract_selectors(css):
    try:
        return re.findall(r'([^{]+){', css)
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
        
        return float(len(removed) / len(initial))
    except Exception:
        return 0.0