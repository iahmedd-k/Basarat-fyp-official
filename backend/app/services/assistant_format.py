"""Plain-text formatting for Basarat Assistant replies (non-markdown UI)."""

from __future__ import annotations

import re


def format_assistant_plain_text(text: str) -> str:
    """Normalize LLM output for a plain-text chat bubble (pre-wrap).

    Goals:
    - Readable short paragraphs and numbered/hyphen lists
    - No markdown artifacts (**, *, #, ```, //) leaking to the UI
    - Fix common glued sentences/list items from compact model output
    """
    if not text:
        return text

    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # Drop fenced code blocks / leftover fence markers (keep inner text)
    t = re.sub(r"```[\w+-]*\n?", "", t)
    t = t.replace("```", "")

    # Strip // comment noise that sometimes appears after formatting attempts
    t = re.sub(r"(?m)^\s*//\s*\*?\s*", "", t)
    t = t.replace("// *", " ").replace("//*", " ")
    t = re.sub(r"\s+//\s+", " ", t)

    # Emphasis / headers
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r"(?m)^#{1,6}\s*", "", t)
    t = re.sub(r"(?<!\w)\*([^*\n]{1,80})\*(?!\w)", r"\1", t)
    t = re.sub(r"(?<!\w)_([^_\n]{1,80})_(?!\w)", r"\1", t)

    # Bullets: *, • at line start → hyphen (never leave raw *)
    t = re.sub(r"(?m)^[ \t]*[\*\u2022]\s+", "- ", t)
    # Orphan bullet markers mid-line that look like list starts
    t = re.sub(r"([.!?])\s*[\*\u2022]\s+", r"\1\n- ", t)

    # Glued numbered lists: "payout.2. Fundamentals" / "Mind1. Valuation"
    # Do NOT match decimals like "415.44. Weight" (digit before the first '.')
    t = re.sub(r"([A-Za-z\)])\.(\d{1,2})\.\s+", r"\1.\n\n\2. ", t)
    t = re.sub(r"([A-Za-z])(\d{1,2})\.\s+", r"\1\n\n\2. ", t)
    # "Portfolio status:1. LUCK"
    t = re.sub(r"([A-Za-z]):(\d{1,2})\.\s+", r"\1:\n\n\2. ", t)

    # Numbered items stuck on the same line: "... data. 2. Fundamentals"
    # Require the list index to be a small integer followed by space+letter (not another digit)
    t = re.sub(r"([^\n\d])[ \t]+(\d{1,2})\.\s+(?=[A-Za-z])", r"\1\n\n\2. ", t)

    # Section headers glued after a sentence (Title Case phrase, 2+ words)
    t = re.sub(
        r"([a-z0-9\)])\.((?:[A-Z][A-Za-z0-9%/&-]*)(?:\s+[A-Z][A-Za-z0-9%/&-]*){1,6}:?)",
        r"\1.\n\n\2",
        t,
    )
    # Same when glued without a period: "...junkYour Current Portfolio"
    t = re.sub(
        r"([a-z])((?:Your Current Portfolio|Key Factors|Portfolio Summary|Important Notes)\b)",
        r"\1\n\n\2",
        t,
    )

    # Hyphen bullets glued after sentence end
    t = re.sub(r"([.!?])[ \t]+-\s+", r"\1\n- ", t)

    # Ensure blank line before a line that looks like a section title ending with ':'
    t = re.sub(r"([^\n])\n([A-Z][^\n]{0,60}:)\s*\n", r"\1\n\n\2\n", t)

    # Space after period/comma when missing before a letter (conservative)
    t = re.sub(r"([a-z])\.([A-Z])", r"\1. \2", t)
    t = re.sub(r",([A-Za-z])", r", \1", t)

    # Collapse whitespace noise but keep intentional blank lines
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    return t.strip()


def strip_markdown_light(text: str) -> str:
    """Lightweight strip for streaming chunks (avoid heavy reflow mid-token)."""
    if not text:
        return text
    return (
        text.replace("**", "")
        .replace("__", "")
        .replace("```", "")
        .replace("// *", "")
        .replace("//*", "")
    )
