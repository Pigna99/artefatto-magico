"""Pacchetto DB: schema, modelli, Database con mixin per sezione.

Importa tutto dal namespace `db` per retrocompatibilità:
    from db import Database, Lore, CodexEntry
"""
from .models import Lore, CodexEntry
from .core import Database

__all__ = ["Database", "Lore", "CodexEntry"]
