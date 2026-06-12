"""P2-C: Obsidian Markdown export utilities — filename sanitization, frontmatter, wiki links."""

from __future__ import annotations

import re
from collections import OrderedDict

# Windows 非法文件名字符
_FILENAME_ILLEGAL = re.compile(r'[\\/:*?"<>|]')
# Emoji and other symbols that cause GBK encoding issues on Windows
_NON_FILENAME_SAFE = re.compile(
    r'[\U0001F300-\U0001F9FF'  # Emoticons, symbols, pictograms
    r'\U00002600-\U000027BF'   # Misc symbols (includes ⚡ U+26A1)
    r'\U0001F000-\U0001F02F'   # Mahjong, domino
    r'\U0001F0A0-\U0001F0FF'   # Playing cards
    r'\U0001F100-\U0001F64F'   # Enclosed, emoticons
    r'\U0001F680-\U0001F6FF'   # Transport
    r'\U0001F900-\U0001F9FF'   # Supplemental symbols
    r'☀-➿'           # Misc symbols
    r'⭐⭕'            # Stars
    r'〰〽'            # Wavy dash
    r'️'                  # Variation selector-16 (emoji presentation)
    r']+'
)


def sanitize_filename(name: str) -> str:
    """清理 Windows 非法字符和 emoji，限制长度。"""
    sanitized = _FILENAME_ILLEGAL.sub("-", name)
    sanitized = _NON_FILENAME_SAFE.sub("", sanitized)
    # Collapse multiple hyphens/spaces
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    # Limit total length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized


def build_frontmatter(fields: OrderedDict | dict) -> str:
    """Build YAML frontmatter block from key-value dict.

    Args:
        fields: OrderedDict of key-value pairs. Lists are serialized as YAML list.
    """
    lines = ["---"]
    for key, val in fields.items():
        if val is None or val == "":
            lines.append(f"{key}:")
        elif isinstance(val, list):
            if val:
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: []")
        elif isinstance(val, bool):
            lines.append(f"{key}: {str(val).lower()}")
        elif isinstance(val, str) and _needs_quoting(val):
            lines.append(f'{key}: "{val}"')
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)


def _needs_quoting(val: str) -> bool:
    """Check if YAML value needs double-quoting."""
    return any(c in val for c in [":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "-", "<", ">", "=", "!", "%", "@", "`", '"', "'"])


def wiki_link(name: str) -> str:
    """Generate Obsidian wiki link. Empty name returns empty string."""
    if not name or not name.strip():
        return ""
    sanitized = sanitize_filename(name.strip())
    # Avoid empty after sanitization
    if not sanitized:
        return ""
    return f"[[{sanitized}]]"


def wiki_links_from_list(items: list[str]) -> str:
    """Generate space-separated wiki links from a list of names."""
    links = [wiki_link(item) for item in items if item]
    return " ".join(links)


# Entities that should generate wiki links
_WIKI_LINK_ENTITY_TYPES = frozenset({
    "company", "technology", "industry_theme", "product_or_model", "person", "organization"
})
