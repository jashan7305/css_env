from .utils import extract_css_val, px_to_num

# this grader checks if the spacing values are in 4px grid multiples . 

def grade(html, css, tokens, state=None):
    try:
        state = state or {}
        props = ['margin', 'padding', 'gap']
        values = extract_css_val(css, props)
        nums = []
        
        for _, val in values:
            parts = val.split()
            for p in parts:
                if "px" in p:
                    try:
                        nums.append(px_to_num(p))
                    except (ValueError, TypeError):
                        pass
        
        if not nums:
            return 1.0
        
        token_spacing = set(tokens.get("spacing", {}).values())
        
        if not token_spacing:
            return 0.0
        
        valid = sum(1 for n in nums if n in token_spacing) # counts the valida values 
        
        return float(valid / len(nums))
    except Exception:
        return 0.0