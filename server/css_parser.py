import tinycss2

def parse_css(css: str):
    """
    Parse CSS string into a list of rules.
    """
    return tinycss2.parse_stylesheet(css, skip_whitespace=True, skip_comments=True)

def serialize_css(rules) -> str:
    """
    Convert parsed rules back into CSS string.
    """
    return tinycss2.serialize(rules)

def get_qualified_rules(rules):
    """
    Get all standard CSS rules (e.g., `.class { ... }`)
    """
    return [r for r in rules if r.type == "qualified-rule"]

def get_media_rules(rules):
    """
    Get all @media rules.
    """
    return [r for r in rules if r.type == "at-rule" and r.at_keyword == "media"]

def get_selector(rule) -> str:
    """
    Extract selector string from a qualified rule.
    """
    return tinycss2.serialize(rule.prelude).strip()

def parse_declarations(rule):
    """
    Extract declarations from a rule.
    """
    return tinycss2.parse_blocks_contents(rule.content)

def get_declaration_map(rule):
    """
    Return dict of property -> value (as string)
    """
    decls = parse_declarations(rule)
    result = {}

    for d in decls:
        if d.type == "declaration" and not d.name.startswith("--"):
            value = tinycss2.serialize(d.value).strip()
            result[d.name] = value

    return result

def find_rules_by_selector(rules, target_selector: str):
    """
    Find all rules matching a selector exactly.
    """
    result = []

    for rule in get_qualified_rules(rules):
        selector = get_selector(rule)
        if selector == target_selector:
            result.append(rule)

    return result

def extract_all_selectors(rules):
    """
    Return a list of all selectors in the stylesheet.
    """
    return [get_selector(r) for r in get_qualified_rules(rules)]

def update_declaration(rule, property_name: str, new_value: str) -> None:
    """
    Update a specific property's value inside a rule.
    """
    tokens = tinycss2.parse_blocks_contents(rule.content)
    parts = []
 
    for token in tokens:
        if token.type == "declaration" and token.name == property_name:
            
            important = " !important" if token.important else ""
            parts.append(f"{property_name}: {new_value}{important}")
        else:
            parts.append(tinycss2.serialize([token]))
 
    rule.content = "; ".join(p for p in parts if p.strip())

def remove_rule_by_selector(rules, target_selector: str):
    """
    Remove all rules matching a selector.
    """
    new_rules = []

    for rule in rules:
        if rule.type == "qualified-rule":
            selector = get_selector(rule)
            if selector == target_selector:
                continue
        new_rules.append(rule)

    return new_rules

def extract_media_queries(rules) -> list:
    """
    Returns list of (condition_string, inner_rules) for all @media blocks.
    """
    media_rules = []
 
    for rule in get_media_rules(rules):
        condition = tinycss2.serialize(rule.prelude).strip()
 
        inner_rules = tinycss2.parse_stylesheet(
            tinycss2.serialize(rule.content),
            skip_whitespace=True,
            skip_comments=True,
        )
 
        media_rules.append((condition, inner_rules))
 
    return media_rules

def has_layout_properties(rule, layout_props):
    """
    Check if a rule contains layout-affecting properties.
    """
    decls = parse_declarations(rule)

    for d in decls:
        if d.type == "declaration" and d.name in layout_props:
            return True

    return False