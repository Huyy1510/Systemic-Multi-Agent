import ast
from typing import Any


def clean_llm_text(content: Any) -> str:
    """Safely extract and clean plain text from LLM responses (str, list of dicts, or AIMessage content)."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and "text" in p:
                parts.append(str(p["text"]))
            elif hasattr(p, "text"):
                parts.append(str(getattr(p, "text")))
        text = "".join(parts)
    elif hasattr(content, "content"):
        return clean_llm_text(getattr(content, "content"))
    else:
        text = str(content)

    text = text.strip()

    # Handle stringified python list representation "[{'type': 'text', 'text': '...'}]"
    if (text.startswith("[{'type':") or text.startswith('[{"type":')) and "text" in text:
        try:
            parsed = ast.literal_eval(text)
            if (
                isinstance(parsed, list)
                and len(parsed) > 0
                and isinstance(parsed[0], dict)
                and "text" in parsed[0]
            ):
                text = parsed[0]["text"]
        except Exception:
            pass

    # Normalize literal \n escapes if they exist without real newlines
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")

    return text.strip()
