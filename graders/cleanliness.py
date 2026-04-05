import re

def extract_selectors(css):
    return re.findall(r'([^{]+){', css)

def grade(html, css, tokens, state=None):
    initial= set(state.get("initial_unused_selectors", []))
    current = set(extract_selectors(css))
    removed=initial - current

    if not initial:
        return 1.0
    
    return len(removed)/len(initial)