# utils/false_positive_filter.py

import os
import re

def is_nonpublic(source_dir: str, function_name: str) -> bool:
    """
    Returns True if `function_name` is declared `private` or `internal` in any .sol file
    under source_dir.
    """
    if not function_name:
        return False

    pattern = re.compile(
        rf"function\s+{re.escape(function_name)}\b[^\)]*\)\s+(private|internal)\b",
        re.IGNORECASE
    )

    for root, _, files in os.walk(source_dir):
        for fname in files:
            if not fname.endswith(".sol"):
                continue
            path = os.path.join(root, fname)
            try:
                code = open(path, "r", encoding="utf-8").read()
            except Exception:
                continue

            if pattern.search(code):
                return True

    return False


def has_modifier_guard(source_dir: str, function_name: str) -> bool:
    """
    Returns True if `function_name` has an `onlyOwner`, `onlyAdmin`, or `onlyRole` modifier
    in its declaration line under any .sol file in source_dir.
    """
    if not function_name:
        return False

    # Look for lines like:
    #   function fnName(...) public onlyOwner { ... }
    #   function fnName(...) external onlyAdmin { ... }
    #   function fnName(...) external onlyRole(ADMIN) { ... }
    pattern = re.compile(
        rf"function\s+{re.escape(function_name)}\b[^\)]*\)\s*(public|external)\s+(onlyOwner|onlyAdmin|onlyRole)\b",
        re.IGNORECASE
    )

    for root, _, files in os.walk(source_dir):
        for fname in files:
            if not fname.endswith(".sol"):
                continue
            path = os.path.join(root, fname)
            try:
                code = open(path, "r", encoding="utf-8").read()
            except Exception:
                continue

            if pattern.search(code):
                return True

    return False


def has_manual_owner_check(source_dir: str, function_name: str) -> bool:
    """
    Returns True if, inside the body of `function_name`, there is a check like
    `require(msg.sender == owner)` or similar patterns. This catches manual owner checks
    that Slither’s `has_modifier_guard` would miss.

    We look for:
      - `msg.sender == owner` or `owner == msg.sender`
      - `require(msg.sender == owner` (anywhere in the function body)
      - `hasRole(` (common OpenZeppelin AccessControl pattern)
    """
    if not function_name:
        return False

    # Roughly match the function definition and capture its body up to the matching brace.
    # This is a simplistic approach and may break on deeply nested braces,
    # but it works in most flattened sources.
    func_block_pattern = re.compile(
        rf"function\s+{re.escape(function_name)}\b[^\)]*\)\s*(public|external)\s*[^\{{]*\{{",
        re.IGNORECASE
    )

    for root, _, files in os.walk(source_dir):
        for fname in files:
            if not fname.endswith(".sol"):
                continue
            path = os.path.join(root, fname)
            try:
                code = open(path, "r", encoding="utf-8").read()
            except Exception:
                continue

            # Find the start index of "function fnName(...) {..."
            match = func_block_pattern.search(code)
            if not match:
                continue

            # Starting from the open brace of this function, extract until the matching closing brace.
            start = match.end() - 1  # position of "{"
            brace_counter = 0
            body = ""
            for i in range(start, len(code)):
                c = code[i]
                body += c
                if c == "{":
                    brace_counter += 1
                elif c == "}":
                    brace_counter -= 1
                    if brace_counter == 0:
                        break

            # Now `body` contains everything from that first "{" to its matching "}".
            # Look for patterns inside that snippet:
            if re.search(r"msg\.sender\s*==\s*owner", body, re.IGNORECASE):
                return True
            if re.search(r"owner\s*==\s*msg\.sender", body, re.IGNORECASE):
                return True
            # Catch OZ AccessControl style: `require(hasRole(ADMIN_ROLE, msg.sender))`
            if re.search(r"hasRole\s*\(", body, re.IGNORECASE):
                return True

    return False
