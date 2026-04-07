import re


 # random design elements taken care of by this grader  
def grade(html, css, tokens, state=None):
    if not css.strip():
        return 1.0

    score = 1.0

    gradients = len(re.findall(r"gradient", css))
    max_gradients = 1
    if gradients > max_gradients:
        score -= 0.10 * (gradients - max_gradients)

    colors = re.findall(r"#(?:[0-9a-fA-F]{6})", css)
    unique_colors = set(colors)
    max_colors = 6
    if len(unique_colors) > max_colors:
        score -= 0.05 * (len(unique_colors) - max_colors)

    sizes = re.findall(r"font-size\s*:\s*([^;]+);", css)
    unique_sizes = set(sizes)
    max_sizes = 4
    if len(unique_sizes) > max_sizes:
        score -= 0.05 * (len(unique_sizes) - max_sizes)

    borders = len(re.findall(r"border[^:]*:", css))
    max_borders = 3
    if borders > max_borders:
        score -= 0.05 * (borders - max_borders)

    abs_pos = len(re.findall(r"position\s*:\s*absolute", css))
    max_abs = 2
    if abs_pos > max_abs:
        score -= 0.10 * (abs_pos - max_abs)

    small_shapes = len(re.findall(
        r"width\s*:\s*[0-9]{1,2}px;\s*height\s*:\s*[0-9]{1,2}px;",
        css
    ))
    max_small = 2
    if small_shapes > max_small:
        score -= 0.05 * (small_shapes - max_small)

    circles = len(re.findall(r"border-radius\s*:\s*50%", css))
    max_circles = 2
    if circles > max_circles:
        score -= 0.05 * (circles - max_circles)

    shadow_count = len(re.findall(r"box-shadow\s*:", css))
    if shadow_count > 3:
        score -= 0.05 * (shadow_count - 3)

    pill_radius = len(re.findall(r"border-radius\s*:\s*9999px", css))
    if pill_radius > 0:
        score -= 0.08 * pill_radius

    return max(0.0, min(1.0, score))