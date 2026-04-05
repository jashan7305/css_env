import random
import re
from typing import Optional

import tinycss2

from .css_parser import (
    get_declaration_map,
    get_qualified_rules,
    get_selector,
    parse_css,
    serialize_css,
    update_declaration,
)


_COLOR_PROPS = {
    "color", "background-color", "background", "border-color",
    "border-top-color", "border-right-color", "border-bottom-color",
    "border-left-color", "outline-color", "fill", "stroke",
}

_SPACING_PROPS = {
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "gap", "row-gap", "column-gap",
}

_FONT_SIZE_PROPS = {"font-size"}
_LINE_HEIGHT_PROPS = {"line-height"}

_GRADIENT_RE = re.compile(r"(linear|radial|conic)-gradient", re.IGNORECASE)
_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_PX_VALUE_RE = re.compile(r"\b(\d+)px\b")
_REM_VALUE_RE = re.compile(r"\b(\d+(?:\.\d+)?)rem\b")

_UNUSED_RULE_POOL = [
    ".tooltip-inner", ".tooltip-arrow", ".popover-body", ".popover-header",
    ".badge-secondary", ".badge-pill", ".breadcrumb-item", ".breadcrumb-item.active",
    ".dropdown-divider", ".dropdown-header", ".dropdown-item.disabled",
    ".modal-backdrop", ".modal-footer", ".modal-dialog", ".offcanvas-backdrop",
    ".spinner-border", ".spinner-grow", ".placeholder-glow",
    ".visually-hidden", ".stretched-link", ".clearfix", ".vr",
    ".ratio", ".ratio-16x9", ".ratio-4x3",
    ".was-validated", ".needs-validation", ".invalid-feedback", ".valid-feedback",
]

_FILLER_DECLARATIONS = [
    "display: block; padding: 6px 11px; font-size: 0.82rem;",
    "position: absolute; top: 0; left: 0; opacity: 0.5;",
    "color: #6c757d; background-color: transparent; border: 1px solid #dee2e6;",
    "width: 100%; height: 2px; overflow: hidden; background: #e9ecef;",
    "margin: 3px 0; border-top: 1px solid rgba(0,0,0,.15);",
]


# =========================
# MAIN ENTRYPOINT
# =========================

def inject_flaws(css: str, tokens: dict, config: dict, seed: int) -> dict:
    """Inject flaws into clean CSS and return flawed css, manifest, and hints."""
    random.seed(seed)
    rng = random.Random(seed)

    rules = parse_css(css)
    manifest = []

    if config.get("wrong_colors"):
        _inject_wrong_colors(rules, tokens, config, rng, manifest)

    if config.get("bad_spacing"):
        _inject_bad_spacing(rules, tokens, config, rng, manifest)

    if config.get("wrong_typography"):
        _inject_wrong_typography(rules, tokens, config, rng, manifest)

    if config.get("broken_contrast"):
        _inject_broken_contrast(rules, tokens, config, rng, manifest)

    if config.get("missing_breakpoints"):
        _inject_missing_breakpoints(rules, manifest)

    if config.get("unused_rules"):
        _inject_unused_rules(rules, rng, manifest)

    return {
        "css": serialize_css(rules),
        "manifest": manifest,
        "hints": [r["description"] for r in manifest],
    }


# =========================
# COLOR FLAWS
# =========================

def _inject_wrong_colors(rules, tokens, config, rng, manifest):
    """Shift token-matching hex colors by a small seeded amount."""
    token_colors = {c.lower() for c in tokens.get("colors", [])}
    intensity = config.get("intensity", 0.8)

    for rule in get_qualified_rules(rules):
        selector = get_selector(rule)
        decl_map = get_declaration_map(rule)

        for prop, val in decl_map.items():
            if prop not in _COLOR_PROPS:
                continue
            if _GRADIENT_RE.search(val):
                continue
            if rng.random() >= intensity:
                continue

            match = _HEX_RE.search(val)
            if not match:
                continue

            hex_val = "#" + match.group(1)
            if hex_val.lower() not in token_colors:
                continue

            shifted = _shift_hex(hex_val, rng)
            new_val = val.replace(hex_val, shifted)
            update_declaration(rule, prop, new_val)

            manifest.append({
                "flaw_type": "wrong_colors",
                "selector": selector,
                "property": prop,
                "original": hex_val,
                "injected": shifted,
                "description": f"'{prop}' on '{selector}' uses '{shifted}' instead of token color '{hex_val}'.",
            })


def _shift_hex(hex_color: str, rng: random.Random) -> str:
    """Shift a hex color by a small seeded per-channel amount."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return hex_color

    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def shift(ch):
        delta = rng.choice([-1, 1]) * rng.randint(8, 32)
        return max(0, min(255, ch + delta))

    return "#{:02x}{:02x}{:02x}".format(shift(r), shift(g), shift(b))


# =========================
# SPACING FLAWS
# =========================

def _inject_bad_spacing(rules, tokens, config, rng, manifest):
    """Replace on-grid px spacing values with nearby off-grid values."""
    unit = tokens.get("spacing_unit", 4)
    off_grid = [v for v in range(3, 48) if v % unit != 0]
    intensity = config.get("intensity", 0.8)

    for rule in get_qualified_rules(rules):
        selector = get_selector(rule)
        decl_map = get_declaration_map(rule)

        for prop, val in decl_map.items():
            if prop not in _SPACING_PROPS:
                continue
            if rng.random() >= intensity:
                continue

            new_val = val
            changed = False

            for match in _PX_VALUE_RE.finditer(val):
                px = int(match.group(1))
                if px > 0 and px % unit == 0:
                    replacement = rng.choice(off_grid)
                    new_val = new_val.replace(f"{px}px", f"{replacement}px", 1)
                    changed = True

            if changed:
                update_declaration(rule, prop, new_val)
                manifest.append({
                    "flaw_type": "bad_spacing",
                    "selector": selector,
                    "property": prop,
                    "original": val,
                    "injected": new_val,
                    "description": f"'{prop}' on '{selector}' has value '{new_val}' which is not on the {unit}px spacing grid (original: '{val}').",
                })


# =========================
# TYPOGRAPHY FLAWS
# =========================

def _inject_wrong_typography(rules, tokens, config, rng, manifest):
    """Replace token-matching font-size and line-height values with off-scale values."""
    font_sizes = [str(f) for f in tokens.get("font_sizes", [])]
    line_heights = [str(lh) for lh in tokens.get("line_heights", [])]
    intensity = config.get("intensity", 0.8)

    for rule in get_qualified_rules(rules):
        selector = get_selector(rule)
        decl_map = get_declaration_map(rule)

        for prop, val in decl_map.items():

            if prop in _FONT_SIZE_PROPS:
                if rng.random() >= intensity:
                    continue
                match = _REM_VALUE_RE.search(val)
                if not match or match.group(0) not in font_sizes:
                    continue

                new_rem = _shift_rem(float(match.group(1)), font_sizes, rng)
                new_val = val.replace(match.group(0), new_rem)
                update_declaration(rule, prop, new_val)
                manifest.append({
                    "flaw_type": "wrong_typography",
                    "selector": selector,
                    "property": prop,
                    "original": val,
                    "injected": new_val,
                    "description": f"'font-size' on '{selector}' is '{new_val}', not on the type scale (original: '{val}').",
                })

            elif prop in _LINE_HEIGHT_PROPS:
                if rng.random() >= intensity:
                    continue
                if val not in line_heights:
                    continue

                candidates = [lh for lh in ["1.0", "1.1", "1.3", "1.4", "1.6", "1.8", "2.2"] if lh not in line_heights]
                if not candidates:
                    continue

                new_val = rng.choice(candidates)
                update_declaration(rule, prop, new_val)
                manifest.append({
                    "flaw_type": "wrong_typography",
                    "selector": selector,
                    "property": prop,
                    "original": val,
                    "injected": new_val,
                    "description": f"'line-height' on '{selector}' is '{new_val}', not a token value (original: '{val}').",
                })


def _shift_rem(original: float, font_sizes: list, rng: random.Random) -> str:
    """Shift a rem value off the type scale by a small seeded amount."""
    token_floats = set()
    for fs in font_sizes:
        m = _REM_VALUE_RE.search(fs)
        if m:
            token_floats.add(round(float(m.group(1)), 3))

    for _ in range(20):
        delta = rng.choice([-1, 1]) * round(rng.uniform(0.05, 0.15), 2)
        candidate = round(original + delta, 2)
        if candidate > 0 and candidate not in token_floats:
            return f"{candidate}rem"

    return f"{round(original + 0.1, 2)}rem"


# =========================
# CONTRAST FLAWS
# =========================

def _inject_broken_contrast(rules, tokens, config, rng, manifest):
    """Shift foreground color toward background until contrast drops below WCAG AA."""
    intensity = config.get("intensity", 0.8)

    for rule in get_qualified_rules(rules):
        selector = get_selector(rule)
        decl_map = get_declaration_map(rule)

        fg_raw = decl_map.get("color")
        bg_raw = decl_map.get("background-color")

        if not fg_raw or not bg_raw:
            continue
        if rng.random() >= intensity:
            continue

        fg_hex = _extract_hex(fg_raw)
        bg_hex = _extract_hex(bg_raw)

        if not fg_hex or not bg_hex:
            continue

        ratio = _contrast_ratio(fg_hex, bg_hex)
        if ratio < 4.5:
            continue

        new_fg = _shift_toward(fg_hex, bg_hex, steps=rng.randint(3, 7))
        new_ratio = _contrast_ratio(new_fg, bg_hex)

        if new_ratio >= 4.5:
            continue

        update_declaration(rule, "color", new_fg)
        manifest.append({
            "flaw_type": "broken_contrast",
            "selector": selector,
            "property": "color",
            "original": fg_hex,
            "injected": new_fg,
            "description": f"'color' on '{selector}' is '{new_fg}' against background '{bg_hex}': contrast ratio {new_ratio:.2f} (below WCAG AA 4.5). Original was '{fg_hex}' (ratio {ratio:.2f}).",
        })


def _shift_toward(fg: str, bg: str, steps: int) -> str:
    """Move fg toward bg by steps * 10 per channel."""
    fg_r, fg_g, fg_b = _hex_to_rgb(fg)
    bg_r, bg_g, bg_b = _hex_to_rgb(bg)

    def move(fc, bc):
        direction = 1 if bc > fc else -1
        return max(0, min(255, fc + direction * steps * 10))

    return "#{:02x}{:02x}{:02x}".format(move(fg_r, bg_r), move(fg_g, bg_g), move(fg_b, bg_b))


# =========================
# BREAKPOINT FLAWS
# =========================

def _inject_missing_breakpoints(rules, manifest):
    """Remove all @media blocks from the stylesheet."""
    surviving = []

    for rule in rules:
        if rule.type == "at-rule" and rule.at_keyword == "media":
            condition = tinycss2.serialize(rule.prelude).strip()
            manifest.append({
                "flaw_type": "missing_breakpoints",
                "selector": None,
                "property": None,
                "original": condition,
                "injected": None,
                "description": f"Media query '@media {condition}' was removed. No responsive rules are present.",
            })
        else:
            surviving.append(rule)

    rules[:] = surviving


# =========================
# UNUSED RULES
# =========================

def _inject_unused_rules(rules, rng, manifest):
    """Append 2 to 5 unused CSS rules with realistic-looking selectors."""
    count = rng.randint(2, 5)
    chosen = rng.sample(_UNUSED_RULE_POOL, min(count, len(_UNUSED_RULE_POOL)))
    new_rule_strings = []

    for selector in chosen:
        declarations = rng.choice(_FILLER_DECLARATIONS)
        new_rule_strings.append(f"{selector} {{ {declarations} }}")
        manifest.append({
            "flaw_type": "unused_rules",
            "selector": selector,
            "property": None,
            "original": None,
            "injected": declarations,
            "description": f"Rule for '{selector}' has no matching element in the HTML and should be removed.",
        })

    rules.extend(parse_css("\n".join(new_rule_strings)))


# =========================
# WCAG HELPERS
# =========================

def _contrast_ratio(hex1: str, hex2: str) -> float:
    """Return WCAG 2.1 contrast ratio between two hex colors."""
    l1, l2 = _relative_luminance(hex1), _relative_luminance(hex2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(hex_color: str) -> float:
    """Return WCAG relative luminance for a hex color."""
    r, g, b = _hex_to_rgb(hex_color)

    def linearize(ch):
        c = ch / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _hex_to_rgb(hex_color: str):
    """Convert a hex color to an (r, g, b) tuple, returns (0,0,0) on failure."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return 0, 0, 0
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 0, 0, 0


def _extract_hex(css_value: str) -> Optional[str]:
    """Extract the first hex color from a CSS value string, or None."""
    match = _HEX_RE.search(css_value)
    return "#" + match.group(1) if match else None