"""GPIO effects: LED RGB + buzzer per dare un corpo all'artefatto.

L'artefatto ha tre stati naturali:
  - idle  → LED spento o respiro lento azzurro
  - think → pulsazione azzurra mentre l'LLM elabora
  - speak → verde fisso (con leggera modulazione) mentre il TTS parla

Inoltre il modello può inserire tag nelle risposte:
  [LIGHT:rosso:pulse]  → pulsa rosso
  [LIGHT:viola:on]     → viola fisso
  [LIGHT:off]          → spegne
  [BEEP:short]         → beep singolo corto
  [BEEP:double]        → due beep
  [BEEP:long]          → beep lungo
I tag vengono *consumati* dal parser (rimossi dal testo) prima di mandarlo
al TTS, così l'artefatto non li pronuncia.

Backend:
  GPIO_BACKEND=real (default su Linux con /dev/gpiomem) → gpiozero
  GPIO_BACKEND=mock                                    → solo log/stdout

Pin layout (BCM):
  LED RGB (anodo comune, 3.3V su pin lungo, resistore 220Ω su ogni catodo)
    R = GPIO 17
    G = GPIO 27
    B = GPIO 22
  Active buzzer
    +  = GPIO 18
    -  = GND
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PIN_R = int(os.environ.get("ARTEFATTO_PIN_R", "17"))
PIN_G = int(os.environ.get("ARTEFATTO_PIN_G", "27"))
PIN_B = int(os.environ.get("ARTEFATTO_PIN_B", "22"))
PIN_BUZZ = int(os.environ.get("ARTEFATTO_PIN_BUZZ", "18"))
LED_COMMON_ANODE = os.environ.get("ARTEFATTO_LED_ANODE", "1") == "1"

# Backend selection: "real" o "mock". Default "real" su Linux, "mock" altrove.
DEFAULT_BACKEND = "real" if Path("/dev/gpiomem").exists() else "mock"
BACKEND = os.environ.get("GPIO_BACKEND", DEFAULT_BACKEND)


# ---------------------------------------------------------------------------
# Color presets
# ---------------------------------------------------------------------------

# (r, g, b) in 0..1
COLORS = {
    "off":     (0.0, 0.0, 0.0),
    "rosso":   (1.0, 0.0, 0.0),
    "red":     (1.0, 0.0, 0.0),
    "verde":   (0.0, 1.0, 0.0),
    "green":   (0.0, 1.0, 0.0),
    "blu":     (0.0, 0.0, 1.0),
    "blue":    (0.0, 0.0, 1.0),
    "azzurro": (0.0, 0.7, 1.0),
    "cyan":    (0.0, 1.0, 1.0),
    "viola":   (0.6, 0.0, 1.0),
    "purple":  (0.6, 0.0, 1.0),
    "giallo":  (1.0, 0.8, 0.0),
    "yellow":  (1.0, 0.8, 0.0),
    "arancio": (1.0, 0.4, 0.0),
    "orange":  (1.0, 0.4, 0.0),
    "bianco":  (1.0, 1.0, 1.0),
    "white":   (1.0, 1.0, 1.0),
}


def parse_color(name: str) -> tuple[float, float, float]:
    return COLORS.get(name.lower().strip(), COLORS["bianco"])


# ---------------------------------------------------------------------------
# Backend: hardware reale via gpiozero
# ---------------------------------------------------------------------------

class _RealBackend:
    def __init__(self):
        from gpiozero import RGBLED, Buzzer  # type: ignore
        # gpiozero RGBLED gestisce anodo/catodo via active_high
        self.led = RGBLED(red=PIN_R, green=PIN_G, blue=PIN_B,
                          active_high=not LED_COMMON_ANODE)
        self.buzz = Buzzer(PIN_BUZZ)

    def set_rgb(self, r: float, g: float, b: float):
        self.led.value = (r, g, b)

    def buzz_on(self):
        self.buzz.on()

    def buzz_off(self):
        self.buzz.off()

    def close(self):
        try:
            self.led.close()
        except Exception:
            pass
        try:
            self.buzz.close()
        except Exception:
            pass


class _MockBackend:
    def __init__(self):
        self._last = (0.0, 0.0, 0.0)

    def set_rgb(self, r: float, g: float, b: float):
        if (r, g, b) != self._last:
            print(f"[gpio mock] LED rgb=({r:.2f},{g:.2f},{b:.2f})")
            self._last = (r, g, b)

    def buzz_on(self):
        print("[gpio mock] BUZZ on")

    def buzz_off(self):
        print("[gpio mock] BUZZ off")

    def close(self):
        pass


def _make_backend():
    if BACKEND == "real":
        try:
            return _RealBackend()
        except Exception as e:
            print(f"[gpio] backend reale non disponibile ({e}), fallback mock")
            return _MockBackend()
    return _MockBackend()


# ---------------------------------------------------------------------------
# Effect engine: stati e animazioni asincroni
# ---------------------------------------------------------------------------

@dataclass
class _State:
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mode: str = "on"  # on | pulse | off
    pulse_period: float = 1.5  # secondi


class GpioFx:
    """Wrapper alto livello: stati semantici (idle/think/speak) + tag."""

    BEEP_PATTERNS = {
        "short":  [(0.05, 0.0)],
        "double": [(0.05, 0.08), (0.05, 0.0)],
        "long":   [(0.4, 0.0)],
        "rise":   [(0.04, 0.06), (0.06, 0.06), (0.10, 0.0)],
    }

    def __init__(self):
        self._b = _make_backend()
        self._state = _State()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    # ---- stati semantici (chiamati dalla TUI) ----------------------------

    def idle(self):
        with self._lock:
            self._state = _State(color=(0.0, 0.0, 0.0), mode="off")

    def thinking(self):
        with self._lock:
            self._state = _State(color=COLORS["azzurro"], mode="pulse",
                                 pulse_period=1.2)

    def speaking(self):
        with self._lock:
            self._state = _State(color=COLORS["verde"], mode="on")

    def error(self):
        with self._lock:
            self._state = _State(color=COLORS["rosso"], mode="pulse",
                                 pulse_period=0.5)

    # ---- tag dal modello -------------------------------------------------

    def apply_light_tag(self, color_name: str, mode: str = "on"):
        rgb = parse_color(color_name)
        with self._lock:
            self._state = _State(color=rgb, mode=mode if mode in ("on", "pulse", "off") else "on",
                                 pulse_period=0.8)

    def beep(self, kind: str = "short"):
        pattern = self.BEEP_PATTERNS.get(kind, self.BEEP_PATTERNS["short"])
        threading.Thread(target=self._play_pattern, args=(pattern,), daemon=True).start()

    def _play_pattern(self, pattern):
        for on_s, off_s in pattern:
            self._b.buzz_on()
            time.sleep(on_s)
            self._b.buzz_off()
            if off_s:
                time.sleep(off_s)

    # ---- thread di rendering --------------------------------------------

    def _run(self):
        TICK = 0.04
        t0 = time.monotonic()
        while not self._stop.is_set():
            with self._lock:
                s = self._state
            r, g, b = s.color
            if s.mode == "off":
                self._b.set_rgb(0, 0, 0)
            elif s.mode == "on":
                self._b.set_rgb(r, g, b)
            else:  # pulse: sin in [0.15..1.0]
                phase = (time.monotonic() - t0) / s.pulse_period
                import math
                k = 0.575 + 0.425 * math.sin(2 * math.pi * phase)
                self._b.set_rgb(r * k, g * k, b * k)
            time.sleep(TICK)
        self._b.set_rgb(0, 0, 0)
        self._b.buzz_off()
        self._b.close()

    def close(self):
        self._stop.set()
        self._t.join(timeout=2)


# ---------------------------------------------------------------------------
# Tag parser: estrae [LIGHT:..] e [BEEP:..] dal testo prima di mandarlo al TTS
# ---------------------------------------------------------------------------

_LIGHT_RE = re.compile(r"\[LIGHT:([a-zA-Zà-ü]+)(?::([a-zA-Z]+))?\]", re.IGNORECASE)
_BEEP_RE = re.compile(r"\[BEEP:([a-zA-Z]+)\]", re.IGNORECASE)


def consume_tags(text: str, fx: Optional[GpioFx]) -> str:
    """Esegue i tag presenti in `text` (se fx non è None) e ritorna il testo
    pulito da inviare al TTS / mostrare a schermo."""
    def _do_light(m: re.Match) -> str:
        if fx:
            fx.apply_light_tag(m.group(1), (m.group(2) or "on").lower())
        return ""

    def _do_beep(m: re.Match) -> str:
        if fx:
            fx.beep(m.group(1).lower())
        return ""

    text = _LIGHT_RE.sub(_do_light, text)
    text = _BEEP_RE.sub(_do_beep, text)
    return text


# ---------------------------------------------------------------------------
# Self-test: cicla colori e beep, poi termina.
# ---------------------------------------------------------------------------

def _selftest():
    print(f"backend: {BACKEND}")
    fx = GpioFx()
    try:
        for name in ("rosso", "verde", "blu", "azzurro", "viola", "giallo", "bianco"):
            print(f"  → {name}")
            fx.apply_light_tag(name, "on")
            time.sleep(0.6)
        print("  → pulse rosso 3s")
        fx.apply_light_tag("rosso", "pulse")
        time.sleep(3)
        print("  → beep short")
        fx.beep("short"); time.sleep(0.6)
        print("  → beep double")
        fx.beep("double"); time.sleep(0.6)
        print("  → beep long")
        fx.beep("long"); time.sleep(0.8)
        print("  → idle")
        fx.idle()
        time.sleep(1)
        print("  → thinking 2s")
        fx.thinking()
        time.sleep(2)
        print("  → speaking 1.5s")
        fx.speaking()
        time.sleep(1.5)
        print("  → idle / fine")
        fx.idle()
        time.sleep(0.5)
    finally:
        fx.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        _selftest()
    else:
        print(__doc__)
        print(f"\nUso: python {sys.argv[0]} test")
