"""Backend hardware (gpiozero) e mock. Astrae il LED RGB, LED turbo, buzzer."""
from __future__ import annotations

import time

from .config import (
    BACKEND, BUZZ_TYPE, LED_COMMON_ANODE, LED_GAIN_B, LED_GAIN_G, LED_GAIN_R,
    LED_INVERT, PIN_B, PIN_BUZZ, PIN_G, PIN_R, PIN_TURBO,
)


class _RealBackend:
    """Hardware reale via gpiozero. LED e buzzer sono indipendenti."""

    def __init__(self):
        self.led = None
        self.led_r = None
        self.led_g = None
        self.led_b = None
        self.led_turbo = None
        self.buzz_active = None
        self.buzz_tonal = None
        try:
            from gpiozero import PWMLED  # type: ignore
            self.led_r = PWMLED(PIN_R, active_high=True)
            self.led_g = PWMLED(PIN_G, active_high=True)
            self.led_b = PWMLED(PIN_B, active_high=True)
            self.led = True
        except Exception as e:
            print(f"[gpio] LED non inizializzato ({e}); LED disabilitato")
        try:
            from gpiozero import LED  # type: ignore
            self.led_turbo = LED(PIN_TURBO, active_high=True)
        except Exception as e:
            print(f"[gpio] LED turbo non inizializzato ({e})")
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
        if self.led is None:
            return
        invert = LED_COMMON_ANODE
        if LED_INVERT:
            invert = not invert
        if invert:
            r, g, b = 1.0 - r, 1.0 - g, 1.0 - b
        self.led_r.value = max(0.0, min(1.0, r * LED_GAIN_R))
        self.led_g.value = max(0.0, min(1.0, g * LED_GAIN_G))
        self.led_b.value = max(0.0, min(1.0, b * LED_GAIN_B))

    def play_tone(self, freq_hz: float, duration_s: float):
        if self.buzz_tonal is not None:
            try:
                from gpiozero.tones import Tone  # type: ignore
                # TonalBuzzer ha range limitato (220-880Hz tipico).
                # Clamp invece di sollevare per evitare silenzi su
                # pattern come 'chirp' che usano 1200-1500Hz.
                clamped = max(220.0, min(880.0, float(freq_hz)))
                self.buzz_tonal.play(Tone(int(clamped)))
                time.sleep(duration_s)
                self.buzz_tonal.stop()
            except Exception as e:
                try:
                    from config import log_event
                    log_event("gpio.tone.err", freq=int(freq_hz),
                              err=repr(e)[:120])
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

    def set_turbo(self, on: bool):
        if self.led_turbo is not None:
            if on:
                self.led_turbo.on()
            else:
                self.led_turbo.off()

    def close(self):
        for obj in (self.led_r, self.led_g, self.led_b, self.led_turbo,
                    self.buzz_tonal, self.buzz_active):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass


class _MockBackend:
    """Backend stub per sviluppo senza hardware."""

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

    def set_turbo(self, on: bool):
        print(f"[gpio mock] turbo LED {'ON' if on else 'off'}")

    def close(self):
        pass


def make_backend():
    if BACKEND == "real":
        try:
            return _RealBackend()
        except Exception as e:
            print(f"[gpio] backend reale non disponibile ({e}), fallback mock")
            return _MockBackend()
    return _MockBackend()
