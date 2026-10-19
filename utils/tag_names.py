"""Shared tag name normalization and validation rules.

Used by the API schema, the memory service, and the SQLite write entry so every
layer applies identical constraints. Names are stored in their normalized form;
uniqueness is enforced by the `tags.name UNIQUE COLLATE NOCASE` constraint,
which only covers ASCII case. Request-level dedupe therefore uses `casefold()`
and must stay consistent with that constraint for English case variants.
"""

import unicodedata
from typing import List

MAX_TAG_NAME_LENGTH = 24
MAX_TAGS_PER_MEMORY = 10


def normalize_tag_name(raw: object) -> str:
    """Return the canonical form of one tag name or raise ValueError."""
    if not isinstance(raw, str):
        raise ValueError("Tag names must be strings")
    # str.split() without arguments strips the edges and collapses every
    # whitespace run (including tabs/newlines) into single separators.
    name = " ".join(raw.split())
    if not name:
        raise ValueError("Tag name must not be blank")
    if len(name) > MAX_TAG_NAME_LENGTH:
        raise ValueError(
            f"Tag name must not exceed {MAX_TAG_NAME_LENGTH} characters"
        )
    for char in name:
        if unicodedata.category(char) == "Cc":
            raise ValueError("Tag name must not contain control characters")
    return name


def normalize_tag_names(names: object) -> List[str]:
    """Normalize a request's tag list: dedupe case-insensitively, keep order."""
    if names is None or isinstance(names, (str, bytes)) or not hasattr(names, "__iter__"):
        raise ValueError("Tags must be a list of strings")
    normalized: List[str] = []
    seen = set()
    for raw in names:
        name = normalize_tag_name(raw)
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(name)
    if len(normalized) > MAX_TAGS_PER_MEMORY:
        raise ValueError(
            f"A memory can have at most {MAX_TAGS_PER_MEMORY} tags"
        )
    return normalized
