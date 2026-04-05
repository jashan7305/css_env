import re 

# this grader checks if the text and bg are contrasting well i.e. readablity 

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def luminance(r,g,b):
    def f(c):
        return c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    
    r, g, b = f(r), f(g), f(b)

    return 0.2126*r + 0.7152*g + 0.0722*b


def contrast_ratio(l1, l2):
    L1=luminance(*hex_to_rgb(l1))
    L2=luminance(*hex_to_rgb(l2))

    L1,L2=max(L1, L2), min(L1, L2)
    return (L1+0.05)/(L2+0.05)


def grade(html, css, tokens, state=None):

    colors = re.findall(r"#(?:[0-9a-fA-F]{6})", css)

    if len(colors) < 2:
        return 1.0

    pairs = list(zip(colors[::2], colors[1::2]))

    valid = sum(1 for fg, bg in pairs if contrast_ratio(fg, bg) >= 4.5)

    return valid / len(pairs)