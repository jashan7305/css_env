from typing import Tuple

try:
    from ..models import CssAction
    from .css_parser import (
        parse_css,
        serialize_css,
        get_qualified_rules,
        get_selector,
        get_declaration_map,
        remove_rule_by_selector,
        update_declaration,
    )
except ImportError:
    from models import CssAction
    from css_parser import (
        parse_css,
        serialize_css,
        get_qualified_rules,
        get_selector,
        get_declaration_map,
        remove_rule_by_selector,
        update_declaration,
    )

def apply_action(css: str, action: CssAction) -> Tuple[str, bool]:
    """
    Apply an action to CSS.

    Returns:
        (new_css, changed_flag)
    """
    if action.value is None and action.action_type != "remove_rule":
        return css, False # no operation
    
    rules = parse_css(css)
    og_css = css

    if action.action_type == "replace_color":
        rules = _replace_color(rules, action.target, action.value)

    elif action.action_type == "remove_rule":
        rules = _remove_rule(rules, action.target)

    elif action.action_type == "fix_spacing":
        rules = _fix_spacing(rules, action.target, action.value)

    elif action.action_type == "fix_typography":
        rules = _fix_typography(rules, action.target, action.value)

    elif action.action_type == "fix_contrast":
        rules = _fix_contrast(rules, action.target, action.value)

    elif action.action_type == "add_breakpoint":
        rules = _add_breakpoint(rules, action.target, action.value)

    new_css = serialize_css(rules)

    changed = _has_changed(og_css, new_css)

    return new_css, changed

def _replace_color(rules, target: str, value: str):
    """
    Replace all occurrences of the target color value across the stylesheet.
    """
    for rule in get_qualified_rules(rules):
        decl_map = get_declaration_map(rule)
        for prop, val in decl_map.items():
            if target in val:
                new_val = val.replace(target, value)
                update_declaration(rule, prop, new_val)
 
    return rules

def _remove_rule(rules, selector: str):
    """
    Remove all rules matching the selector.
    """
    return remove_rule_by_selector(rules, selector)

def _fix_spacing(rules, target: str, value: str):
    """
    Fix a specific spacing property on a specific selector.
    """
    try:
        selector, prop = target.rsplit("::", 1)
    except ValueError:
        return rules
 
    for rule in get_qualified_rules(rules):
        if get_selector(rule) == selector:
            update_declaration(rule, prop, value)
 
    return rules

def _fix_typography(rules, target: str, value: str):
    """
    Fix font-size or line-height.
    target format: ".title.font-size"
    """
    try:
        selector, prop = target.rsplit(".", 1)
    except ValueError:
        return rules

    for rule in get_qualified_rules(rules):
        if get_selector(rule) == selector:
            update_declaration(rule, prop, value)

    return rules

def _fix_contrast(rules, selector: str, value: str):
    """
    Fix foreground/background color pair.
    value format: "fg_color,bg_color"
    """
    try:
        fg, bg = value.split(",")
    except ValueError:
        return rules

    for rule in get_qualified_rules(rules):
        if get_selector(rule) == selector:
            update_declaration(rule, "color", fg.strip())
            update_declaration(rule, "background-color", bg.strip())

    return rules

def _add_breakpoint(rules, breakpoint: str, css_block: str):
    """
    Add a media query block.

    breakpoint: "768px"
    css_block: ".container { width: 100%; }"
    """
    media_rule = f"@media (max-width: {breakpoint}) {{ {css_block} }}"
    new_rules = parse_css(media_rule)

    return rules + new_rules

def _has_changed(old_css: str, new_css: str) -> bool:
    """
    Detect if CSS actually changed.
    """
    return old_css.strip() != new_css.strip()