import re
from .utils import clamp_open_unit_interval, normalize_hex

def grade(html, css, tokens, state=None):
    try:
        state = state or {}
        token_colors = set(normalize_hex(c) for c in tokens.get("colors", {}).values())
        colors = re.findall(r"#(?:[0-9a-fA-F]{3}){1,2}", css) # extract hex colors
        
        if not colors:
            return clamp_open_unit_interval(1.0)
        
        if not token_colors:
            return clamp_open_unit_interval(0.0)
        
        normalized_colors = [normalize_hex(c) for c in colors]
        matches = sum(1 for c in normalized_colors if c in token_colors)
        
        score = float(matches / len(normalized_colors))
        return clamp_open_unit_interval(score)
    except Exception:
        return clamp_open_unit_interval(0.0)