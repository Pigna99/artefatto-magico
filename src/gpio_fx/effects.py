"""GpioFx: stati semantici (idle/think/speak), mood, signature, flash, beep."""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from .backend import make_backend
from .config import COLORS, parse_color


@dataclass
class _State:
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mode: str = "on"  # on | pulse | off
    pulse_period: float = 1.5


class GpioFx:
    """Wrapper alto livello con thread di rendering interno."""

    BEEP_PATTERNS = {
        # base
        "short":  [(880, 0.08, 0.0)],
        "double": [(880, 0.06, 0.08), (880, 0.06, 0.0)],
        "long":   [(440, 0.45, 0.0)],
        "rise":   [(440, 0.05, 0.04), (660, 0.05, 0.04), (880, 0.10, 0.0)],
        "fall":   [(880, 0.05, 0.04), (660, 0.05, 0.04), (440, 0.10, 0.0)],
        "alarm":  [(1320, 0.10, 0.08), (1320, 0.10, 0.08), (1320, 0.10, 0.0)],
        "low":    [(220, 0.30, 0.0)],
        # R2D2-style
        "chirp":  [(1200, 0.04, 0.02), (1500, 0.04, 0.02), (1100, 0.05, 0.0)],
        "ack":    [(660, 0.06, 0.04), (880, 0.08, 0.0)],
        "deny":   [(660, 0.08, 0.04), (440, 0.15, 0.0)],
        # dadi
        "dice":   [(880, 0.03, 0.02), (660, 0.03, 0.02), (1100, 0.03, 0.02),
                   (550, 0.03, 0.02), (990, 0.03, 0.02), (770, 0.05, 0.0)],
    }

    MOODS = {
        "tensione":  (COLORS["rosso"],   "pulse", 1.8),
        "mistero":   (COLORS["viola"],   "pulse", 2.5),
        "pace":      (COLORS["verde"],   "on",    0.0),
        "battaglia": (COLORS["rosso"],   "pulse", 0.4),
        "magia":     (COLORS["azzurro"], "pulse", 1.0),
        "trionfo":   (COLORS["giallo"],  "on",    0.0),
        "lutto":     (COLORS["blu"],     "pulse", 4.0),
    }

    def __init__(self):
        self._b = make_backend()
        self._state = _State()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    # ---- stati semantici --------------------------------------------------

    def idle(self, color: str = "bianco"):
        with self._lock:
            self._state = _State(color=parse_color(color), mode="pulse", pulse_period=3.0)

    def thinking(self):
        with self._lock:
            self._state = _State(color=COLORS["azzurro"], mode="pulse", pulse_period=1.2)

    def speaking(self):
        with self._lock:
            self._state = _State(color=COLORS["verde"], mode="on")

    def error(self):
        with self._lock:
            self._state = _State(color=COLORS["rosso"], mode="pulse", pulse_period=0.5)

    def mood(self, name: str):
        m = self.MOODS.get(name.lower())
        if m is None:
            return
        color, mode, period = m
        with self._lock:
            self._state = _State(color=color, mode=mode, pulse_period=period or 1.0)

    # ---- signature / notifiche -------------------------------------------

    def boot(self):
        """Fade nero→viola→bianco + beep rise."""
        def _seq():
            self.beep("rise")
            viola = COLORS["viola"]
            for k in range(0, 16):
                t = k / 15.0
                with self._lock:
                    self._state = _State(
                        color=(viola[0] * t, viola[1] * t, viola[2] * t), mode="on")
                time.sleep(0.04)
            for k in range(0, 21):
                t = k / 20.0
                r = viola[0] + (1.0 - viola[0]) * t
                g = viola[1] + (1.0 - viola[1]) * t
                b = viola[2] + (1.0 - viola[2]) * t
                with self._lock:
                    self._state = _State(color=(r, g, b), mode="on")
                time.sleep(0.05)
        threading.Thread(target=_seq, daemon=True).start()

    def shutdown(self):
        def _seq():
            self.beep("fall")
            for k in range(20, -1, -1):
                v = k / 20.0
                with self._lock:
                    self._state = _State(color=(v, v, v), mode="on")
                time.sleep(0.04)
            with self._lock:
                self._state = _State(color=(0, 0, 0), mode="off")
        threading.Thread(target=_seq, daemon=True).start()

    def notify(self):
        """Doppio bip + lampo blu per eventi esterni (Telegram, ecc)."""
        self.beep("double")
        self.flash("blu", 0.4)

    # ---- comandi puntuali -------------------------------------------------

    def flash(self, color_name: str, duration_s: float = 0.25):
        """Lampo che ripristina lo stato precedente."""
        with self._lock:
            prev = self._state
            prev_color = prev.color
            prev_mode = prev.mode
            prev_period = prev.pulse_period
        def _seq():
            with self._lock:
                self._state = _State(color=parse_color(color_name), mode="on")
            time.sleep(duration_s)
            with self._lock:
                self._state = _State(color=prev_color, mode=prev_mode,
                                     pulse_period=prev_period)
        threading.Thread(target=_seq, daemon=True).start()

    def turbo(self, on: bool):
        self._b.set_turbo(on)

    def beep(self, kind: str = "short"):
        pattern = self.BEEP_PATTERNS.get(kind, self.BEEP_PATTERNS["short"])
        threading.Thread(target=self._play_pattern, args=(pattern,), daemon=True).start()

    def _play_pattern(self, pattern):
        for step in pattern:
            if len(step) == 3:
                freq, on_s, off_s = step
            else:
                freq, on_s, off_s = 880.0, step[0], step[1]
            self._b.play_tone(freq, on_s)
            if off_s:
                self._b.silence(off_s)

    # ---- tag inline (chiamati da consume_tags) ----------------------------

    def apply_light_tag(self, color_name: str, mode: str = "on"):
        rgb = parse_color(color_name)
        with self._lock:
            self._state = _State(color=rgb,
                                 mode=mode if mode in ("on", "pulse", "off") else "on",
                                 pulse_period=0.8)

    # ---- audio reattivo (opzionale, futuro) -------------------------------

    def speaking_amplitude(self, level: float):
        level = max(0.0, min(1.0, level))
        v = 0.3 + 0.7 * level
        with self._lock:
            self._state = _State(color=(0.0, v, 0.0), mode="on")

    # ---- thread di rendering ---------------------------------------------

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
            else:  # pulse
                phase = (time.monotonic() - t0) / s.pulse_period
                k = 0.575 + 0.425 * math.sin(2 * math.pi * phase)
                self._b.set_rgb(r * k, g * k, b * k)
            time.sleep(TICK)
        self._b.set_rgb(0, 0, 0)
        self._b.close()

    def close(self):
        self._stop.set()
        self._t.join(timeout=2)
