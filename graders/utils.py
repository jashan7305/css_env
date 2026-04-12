import re
import math


SCORE_EPSILON = 1e-6
MIN_SCORE_BOUND = 0.01
MAX_SCORE_BOUND = 0.99

def extract_css_val(css: str, properies:list):
    pattern = r"("+"|".join(properies)+r")\s*:\s*([^;]+);"
    return re.findall(pattern, css)

def normalize_hex(color:str)->str:   # make the hex format consistent 
    color=color.lower()
    if len(color)== 4:
        color = '#' +''.join([c*2 for c in color[1:]])
    return color

def px_to_num(value: str):
    return int(value.replace('px', '').strip())


def clamp_open_unit_interval(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = MIN_SCORE_BOUND + SCORE_EPSILON
    if not math.isfinite(numeric):
        numeric = MIN_SCORE_BOUND + SCORE_EPSILON
    if numeric <= MIN_SCORE_BOUND:
        numeric = MIN_SCORE_BOUND + SCORE_EPSILON
    if numeric >= MAX_SCORE_BOUND:
        numeric = MAX_SCORE_BOUND - SCORE_EPSILON

    rounded = round(numeric, 2)
    if rounded <= MIN_SCORE_BOUND:
        return 0.02
    if rounded >= MAX_SCORE_BOUND:
        return 0.98
    return float(f"{rounded:.2f}")