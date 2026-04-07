import re 

# this grader checks if the text and bg are contrasting well i.e. readablity 

def hex_to_rgb(hex_color):
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        if len(hex_color) != 6:
            return (0, 0, 0)
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (0, 0, 0)

def luminance(r, g, b):
    try:
        #Normalize RGB values to [0, 1] basically 0-255 to 0-1
        r, g, b = r / 255.0, g / 255.0, b / 255.0
        
        def f(c):
            # Convert sRGB to linear light (gamma correction)
            # 0.03928 → threshold for switching formula
            # 12.92 → linear scaling for dark values
            # 0.055, 1.055 → constants for gamma expansion
            # 2.4 → gamma exponent (human brightness perception)
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        

        # gamma correction for the three chanels
        r, g, b = f(r), f(g), f(b)
        # Compute relative luminance using perceptual weights
        # Human eye sensitivity: Green > Red > Blue
        # 0.2126 (R), 0.7152 (G), 0.0722 (B)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    except Exception:
        return 0.0

def contrast_ratio(l1, l2):
    try:
        L1 = luminance(*hex_to_rgb(l1))
        L2 = luminance(*hex_to_rgb(l2))
        L1, L2 = max(L1, L2), min(L1, L2)
        return (L1 + 0.05) / (L2 + 0.05)
    except Exception:
        return 0.0

def grade(html, css, tokens, state=None):
    try:
        state = state or {}
        rule_blocks = re.findall(r"[^{}]+\{([^{}]+)\}", css)
        if not rule_blocks:
            return 1.0

        evaluations = []
        default_bg = tokens.get("colors", {}).get("white", "#ffffff")

        for block in rule_blocks:
            fg_match = re.search(r"color\s*:\s*(#(?:[0-9a-fA-F]{3}){1,2})", block)
            if not fg_match:
                continue

            bg_match = re.search(r"background-color\s*:\s*(#(?:[0-9a-fA-F]{3}){1,2})", block)
            if not bg_match:
                bg_match = re.search(r"background\s*:\s*(#(?:[0-9a-fA-F]{3}){1,2})", block)

            fg = fg_match.group(1)
            bg = bg_match.group(1) if bg_match else default_bg
            evaluations.append((fg, bg))

        if not evaluations:
            return 1.0

        valid = sum(1 for fg, bg in evaluations if contrast_ratio(fg, bg) >= 4.5)

        score = float(valid / len(evaluations))
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.0