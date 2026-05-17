"""Configurazione GPIO (pin, polarità, gain) + palette colori.

Tutti i valori sono override-abili via env.
"""
from __future__ import annotations

import os
from pathlib import Path


# Pin BCM
PIN_R = int(os.environ.get("ARTEFATTO_PIN_R", "17"))
PIN_G = int(os.environ.get("ARTEFATTO_PIN_G", "27"))
PIN_B = int(os.environ.get("ARTEFATTO_PIN_B", "22"))
PIN_BUZZ = int(os.environ.get("ARTEFATTO_PIN_BUZZ", "18"))
PIN_TURBO = int(os.environ.get("ARTEFATTO_PIN_TURBO", "23"))

# Polarità LED RGB. Vedi CLAUDE.md per la procedura di taratura.
LED_COMMON_ANODE = os.environ.get("ARTEFATTO_LED_ANODE", "1") == "1"
LED_INVERT = os.environ.get("ARTEFATTO_LED_INVERT", "0") == "1"
LED_GAIN_R = float(os.environ.get("ARTEFATTO_LED_GAIN_R", "1.0"))
LED_GAIN_G = float(os.environ.get("ARTEFATTO_LED_GAIN_G", "1.0"))
LED_GAIN_B = float(os.environ.get("ARTEFATTO_LED_GAIN_B", "1.0"))

# Buzzer
BUZZ_TYPE = os.environ.get("ARTEFATTO_BUZZ_TYPE", "passive")

# Backend selection
DEFAULT_BACKEND = "real" if Path("/dev/gpiomem").exists() else "mock"
BACKEND = os.environ.get("GPIO_BACKEND", DEFAULT_BACKEND)


# Palette (r,g,b) in 0..1
COLORS = {
    "off":     (0.0, 0.0, 0.0),
    "rosso":   (1.0, 0.0, 0.0),  "red":     (1.0, 0.0, 0.0),
    "verde":   (0.0, 1.0, 0.0),  "green":   (0.0, 1.0, 0.0),
    "blu":     (0.0, 0.0, 1.0),  "blue":    (0.0, 0.0, 1.0),
    "azzurro": (0.0, 0.7, 1.0),  "cyan":    (0.0, 1.0, 1.0),
    "viola":   (0.6, 0.0, 1.0),  "purple":  (0.6, 0.0, 1.0),
    "giallo":  (1.0, 0.8, 0.0),  "yellow":  (1.0, 0.8, 0.0),
    "arancio": (1.0, 0.4, 0.0),  "orange":  (1.0, 0.4, 0.0),
    "bianco":  (1.0, 1.0, 1.0),  "white":   (1.0, 1.0, 1.0),
}


def parse_color(name: str) -> tuple[float, float, float]:
    return COLORS.get(name.lower().strip(), COLORS["bianco"])
