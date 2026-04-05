from .utils import extract_css_val, px_to_num
# this grader checks if the spacing values in are ona 4px grid 
def grade(html, css, tokens, state=None):
    props=['margin', 'padding', 'gap']
    values=extract_css_val(css, props)
    nums=[]
    for _, val in values:
        parts=val.split()
        for p in parts:
            if "px" in p:
                nums.append(px_to_num(p))


    if not nums:
        return 1.0
    
    valid = sum(1 for n in nums if n in tokens.get("spacing", {}).values()) # counts the valid values

    return valid/len(nums)