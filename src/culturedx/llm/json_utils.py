# src/culturedx/llm/json_utils.py
"""Extract structured JSON from LLM text responses."""
from __future__ import annotations

import json
import re


def extract_json_from_response(text: str) -> dict | list | None:
    """Extract the first valid JSON object or array from LLM output.

    Tries in order:
    1. Parse the entire text as JSON
    2. Extract from markdown code block
    3. Find first { } or [ ] balanced substring
    """
    text = text.strip()

    # Try full parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try markdown code block
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md_match:
        try:
            return json.loads(md_match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # Try finding first balanced JSON
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break
    return None
