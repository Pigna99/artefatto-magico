"""Pulizia testo per TTS + split in frasi.

Il TTS leggerebbe letteralmente asterischi, underscore e simboli markdown.
Li rimuoviamo prima della sintesi.
"""
from __future__ import annotations

import re

SENTENCE_END = re.compile(r"[.!?…](\s|$)")

_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC_AST = re.compile(r"\*([^*]+)\*")
_MD_ITALIC_UND = re.compile(r"_([^_]+)_")
_MD_CODE = re.compile(r"`([^`]+)`")
_MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MD_BULLET = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_MD_RESIDUAL = re.compile(r"[*_`~#]+")


def sanitize_for_tts(text: str) -> str:
    if not text:
        return text
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_ITALIC_AST.sub(r"\1", text)
    text = _MD_ITALIC_UND.sub(r"\1", text)
    text = _MD_CODE.sub(r"\1", text)
    text = _MD_HEADING.sub("", text)
    text = _MD_BULLET.sub("", text)
    text = _MD_RESIDUAL.sub("", text)
    return text


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """Estrae frasi complete da un buffer di streaming. Ritorna (frasi, resto)."""
    sentences = []
    while True:
        m = SENTENCE_END.search(buffer)
        if not m:
            break
        s = buffer[: m.end()].strip()
        buffer = buffer[m.end():]
        if s:
            sentences.append(s)
    return sentences, buffer
