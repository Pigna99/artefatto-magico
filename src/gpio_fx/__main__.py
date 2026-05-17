"""Self-test invocabile come: python -m gpio_fx test"""
from __future__ import annotations

import sys
import time

from .config import BACKEND
from .effects import GpioFx


def selftest():
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
        for kind in ("short", "double", "long", "rise", "fall", "alarm", "low",
                     "chirp", "ack", "deny", "dice"):
            print(f"  → beep {kind}")
            fx.beep(kind)
            time.sleep(1.2)
        print("  → idle"); fx.idle(); time.sleep(1)
        print("  → thinking 2s"); fx.thinking(); time.sleep(2)
        print("  → speaking 1.5s"); fx.speaking(); time.sleep(1.5)
        print("  → idle / fine"); fx.idle(); time.sleep(0.5)
    finally:
        fx.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        selftest()
    else:
        print("Uso: python -m gpio_fx test")
