"""Pacchetto GPIO: LED RGB + buzzer + parser tag inline.

Import retrocompatibili:
    from gpio_fx import GpioFx, consume_tags
"""
from .effects import GpioFx
from .tags import consume_tags

__all__ = ["GpioFx", "consume_tags"]
