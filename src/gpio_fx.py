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
# Tipo di buzzer: "passive" usa PWM tonale (TonalBuzzer), "active" usa on/off.
# Il kit Elegoo include entrambi: il passive (cilindro aperto) e l'active (con
# etichetta sopra). Il passive permette toni veri = effetti più espressivi.
BUZZ_TYPE = os.environ.get("ARTEFATTO_BUZZ_TYPE", "passive")

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
    """Hardware reale. LED e buzzer sono indipendenti: se uno non è cablato,
    quel pezzo va in modalità no-op senza far cadere l'altro."""

    def __init__(self):
        self.led = None
        self.buzz_active = None
        self.buzz_tonal = None
        try:
            from gpiozero import RGBLED  # type: ignore
            self.led = RGBLED(red=PIN_R, green=PIN_G, blue=PIN_B,
                              active_high=not LED_COMMON_ANODE)
        except Exception as e:
            print(f"[gpio] LED non inizializzato ({e}); LED disabilitato")
        try:
            if BUZZ_TYPE == "passive":
                from gpiozero import TonalBuzzer  # type: ignore
                self.buzz_tonal = TonalBuzzer(PIN_BUZZ)
            else:
                from gpiozero import Buzzer  # type: ignore
                self.buzz_active = Buzzer(PIN_BUZZ)
        except Exception as e:
            print(f"[gpio] buzzer non inizializzato ({e}); audio disabilitato")

    def set_rgb(self, r: float, g: float, b: float):
        if self.led is not None:
            self.led.value = (r, g, b)

    def play_tone(self, freq_hz: float, duration_s: float):
        """Suona una nota a freq_hz per duration_s. Se buzzer è active,
        il parametro freq_hz è ignorato (l'active emette la sua frequenza fissa)."""
        if self.buzz_tonal is not None:
            try:
                from gpiozero.tones import Tone  # type: ignore
                self.buzz_tonal.play(Tone(int(freq_hz)))
                time.sleep(duration_s)
                self.buzz_tonal.stop()
            except Exception:
                pass
        elif self.buzz_active is not None:
            self.buzz_active.on()
            time.sleep(duration_s)
            self.buzz_active.off()
        else:
            time.sleep(duration_s)

    def silence(self, duration_s: float):
        time.sleep(duration_s)

    def close(self):
        for obj in (self.led, self.buzz_tonal, self.buzz_active):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass


class _MockBackend:
    def __init__(self):
        self._last = (0.0, 0.0, 0.0)

    def set_rgb(self, r: float, g: float, b: float):
        if (r, g, b) != self._last:
            print(f"[gpio mock] LED rgb=({r:.2f},{g:.2f},{b:.2f})")
            self._last = (r, g, b)

    def play_tone(self, freq_hz: float, duration_s: float):
        print(f"[gpio mock] BUZZ tone {int(freq_hz)}Hz for {duration_s:.2f}s")
        time.sleep(duration_s)

    def silence(self, duration_s: float):
        time.sleep(duration_s)

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

    # Ogni step è (freq_hz, durata_tono_s, pausa_dopo_s)
    # Frequenze ispirate a interfacce sci-fi: 880=A5 alto, 440=A4 medio,
    # 220=A3 grave, 1320=tono allarme.
    BEEP_PATTERNS = {
        "short":  [(880, 0.08, 0.0)],
        "double": [(880, 0.06, 0.08), (880, 0.06, 0.0)],
        "long":   [(440, 0.45, 0.0)],
        "rise":   [(440, 0.05, 0.04), (660, 0.05, 0.04), (880, 0.10, 0.0)],
        "fall":   [(880, 0.05, 0.04), (660, 0.05, 0.04), (440, 0.10, 0.0)],
        "alarm":  [(1320, 0.10, 0.08), (1320, 0.10, 0.08), (1320, 0.10, 0.0)],
        "low":    [(220, 0.30, 0.0)],
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
        for step in pattern:
            # Compatibilità: 3-tupla (freq, on, off) o vecchia 2-tupla (on, off)
            if len(step) == 3:
                freq, on_s, off_s = step
            else:
                freq, on_s, off_s = 880.0, step[0], step[1]
            self._b.play_tone(freq, on_s)
            if off_s:
                self._b.silence(off_s)

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
        for kind in ("short", "double", "long", "rise", "fall", "alarm", "low"):
            print(f"  → beep {kind}")
            fx.beep(kind)
            time.sleep(1.2)
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
