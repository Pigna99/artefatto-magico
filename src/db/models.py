"""Dataclass per le righe del DB."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Lore:
    id: int
    name: str
    kind: str
    description: str
    tags: Optional[str] = None
    # Campi aggiunti con lo schema v2 (sync col sito). Tutti opzionali per
    # retrocompatibilità delle SELECT che ne pescano solo un sottoinsieme.
    secret: int = 0
    sealed: int = 0
    deleted_at: Optional[str] = None
    origin: str = "pi"
    remote_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_context_line(self) -> str:
        tag_part = f" [{self.tags}]" if self.tags else ""
        return f"- {self.kind.upper()} {self.name}{tag_part}: {self.description}"


@dataclass
class CodexEntry:
    id: int
    title: str
    body: str
    happened_at: Optional[str] = None
    tags: Optional[str] = None
    secret: int = 0
    sealed: int = 0
    deleted_at: Optional[str] = None
    origin: str = "pi"
    remote_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_context_line(self) -> str:
        when = f" ({self.happened_at})" if self.happened_at else ""
        body = self.body if len(self.body) <= 200 else self.body[:200] + "..."
        return f"- CODEX{when} {self.title}: {body}"
