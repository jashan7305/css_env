import re 

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