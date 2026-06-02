"""Backend hardware (gpiozero) e mock. Astrae il LED RGB, LED turbo, buzzer."""
from __future__ import annotations

import os
import threading
import time

from .config import (
    BACKEND, BUZZ_TYPE, LED_COMMON_ANODE, LED_GAIN_B, LED_GAIN_G, LED_GAIN_R,
    LED_INVERT, PIN_B, PIN_BUZZ, PIN_G, PIN_R, PIN_TURBO,
)


# Watchdog: ogni N secondi il _RealBackend richiama reinit_buzzer() per
# evitare che il TonalBuzzer scivoli in stato corrotto (sintomo: i toni
# non escono più dopo qualche minuto di uso o dopo eventi rumorosi
# come subprocess+suspend). Disabilita con =0.
BUZZ_WATCHDOG_SEC = int(os.environ.get("ARTEFATTO_BUZZ_WATCHDOG_SEC", "60"))


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
        # Lock condiviso fra play_tone, reinit_buzzer e watchdog: evita
        # che il refresh periodico tagli un beep in corso o che si
        # tenti di ricreare il device mentre sta suonando.
        self._buzz_lock = threading.Lock()
        self._buzz_stop = threading.Event()
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
        if BUZZ_WATCHDOG_SEC > 0:
            t = threading.Thread(target=self._buzz_watchdog, daemon=True)
            t.start()

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

    def reinit_buzzer(self):
        """Ricostruisce il TonalBuzzer dopo che è andato in stato corrotto
        (es. dopo subprocess.run con suspend Textual, o per usura
        periodica gestita dal watchdog).

        Acquisisce _buzz_lock per non interrompere un beep in corso.
        Se è già preso (es. play_tone sta suonando) torna senza far nulla
        — il prossimo ciclo watchdog ritenterà.
        """
        if not self._buzz_lock.acquire(blocking=False):
            return
        try:
            if self.buzz_tonal is not None:
                try:
                    self.buzz_tonal.close()
                except Exception:
                    pass
                self.buzz_tonal = None
            if self.buzz_active is not None:
                try:
                    self.buzz_active.close()
                except Exception:
                    pass
                self.buzz_active = None
            if BUZZ_TYPE == "passive":
                from gpiozero import TonalBuzzer  # type: ignore
                self.buzz_tonal = TonalBuzzer(PIN_BUZZ)
            else:
                from gpiozero import Buzzer  # type: ignore
                self.buzz_active = Buzzer(PIN_BUZZ)
        except Exception as e:
            try:
                from config import log_event
                log_event("gpio.reinit_buzzer.err", err=repr(e)[:120])
            except Exception:
                pass
        finally:
            self._buzz_lock.release()

    def _buzz_watchdog(self):
        """Loop daemon: ogni BUZZ_WATCHDOG_SEC chiama reinit_buzzer().
        Salta automaticamente se il buzzer sta suonando (lock occupato)."""
        try:
            from config import log_event
        except Exception:
            log_event = None  # type: ignore
        while not self._buzz_stop.wait(BUZZ_WATCHDOG_SEC):
            self.reinit_buzzer()
            if log_event is not None:
                try:
                    log_event("gpio.buzz_watchdog.tick")
                except Exception:
                    pass

    def play_tone(self, freq_hz: float, duration_s: float):
        with self._buzz_lock:
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
        self._buzz_stop.set()
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
