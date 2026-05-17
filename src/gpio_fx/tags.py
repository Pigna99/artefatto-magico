"""Parser dei tag inline [LIGHT:..] [BEEP:..] [MOOD:..].

Esegue gli effetti contro un'istanza GpioFx e ritorna il testo ripulito,
pronto per essere passato al TTS."""
from __future__ import annotations

import re
from typing import Optional

from .effects import GpioFx


_LIGHT_RE = re.compile(r"\[LIGHT:([a-zA-Zà-ü]+)(?::([a-zA-Z]+))?\]", re.IGNORECASE)
_BEEP_RE = re.compile(r"\[BEEP:([a-zA-Z]+)\]", re.IGNORECASE)
_MOOD_RE = re.compile(r"\[MOOD:([a-zA-Zà-ü]+)\]", re.IGNORECASE)


def consume_tags(text: str, fx: Optional[GpioFx]) -> str:
    def _do_light(m: re.Match) -> str:
        if fx:
            fx.apply_light_tag(m.group(1), (m.group(2) or "on").lower())
        return ""

    def _do_beep(m: re.Match) -> str:
        if fx:
            fx.beep(m.group(1).lower())
        return ""

    def _do_mood(m: re.Match) -> str:
        if fx:
            fx.mood(m.group(1))
        return ""

    text = _LIGHT_RE.sub(_do_light, text)
    text = _BEEP_RE.sub(_do_beep, text)
    text = _MOOD_RE.sub(_do_mood, text)
    return text
