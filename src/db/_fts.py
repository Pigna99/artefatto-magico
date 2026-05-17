"""Helper FTS5 condivisi tra lore e codex."""
from __future__ import annotations

import re


def fts_words(query: str) -> list[str]:
    """Estrae parole significative (>=3 char) per FTS5/LIKE."""
    return [w for w in re.findall(r"\w+", query.strip(), re.UNICODE) if len(w) >= 3]
