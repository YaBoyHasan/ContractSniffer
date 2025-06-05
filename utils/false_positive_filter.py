# utils/false_positive_filter.py

import re
import os

def has_modifier_guard(source_dir: str, function_name: str) -> bool:
    """
    Return True if `function_name` in any .sol file under source_dir
    contains a known guard modifier (`onlyOwner` or `onlyAdmin`) in its signature or body.
    """
    # 1) Read all .sol files in source_dir into one big string
    code = ""
    for root, _, files in os.walk(source_dir):
        for fname in files:
            if fname.endswith(".sol"):
                try:
                    code += open(os.path.join(root, fname), "r", encoding="utf-8").read() + "\n"
                except:
                    pass

    # 2) Find the function signature for function_name
    #    Pattern: function <function_name>( ... ) [modifiers] { 
    sig_pattern = re.compile(
        rf"function\s+{re.escape(function_name)}\b[^\{{]*\{{", re.IGNORECASE
    )
    match = sig_pattern.search(code)
    if not match:
        return False  # function not found in source

    # 3) Extract the function’s full body (from “{” to matching “}”)
    start = match.end() - 1  # position of the opening brace '{'
    depth = 1
    idx = start + 1
    while idx < len(code) and depth > 0:
        if code[idx] == "{":
            depth += 1
        elif code[idx] == "}":
            depth -= 1
        idx += 1
    body = code[start:idx]

    # 4) Check for “onlyOwner” or “onlyAdmin” in signature or body
    if re.search(r"\bonlyOwner\b", body) or re.search(r"\bonlyAdmin\b", body):
        return True

    return False
