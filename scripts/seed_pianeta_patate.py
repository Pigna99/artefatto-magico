"""Carica nel DB le voci di lore del 'Pianeta Patate' per testare il RAG.

Da lanciare sul Pi:
    /home/pigna/artefatto/.venv/bin/python scripts/seed_pianeta_patate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permette di lanciarlo con cwd = repo root o cwd = scripts/
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from db import Database

DB_PATH = Path.home() / "artefatto" / "data" / "artefatto.db"

ENTRIES = [
    # (kind, name, description, tags)
    ("place", "Pianeta Patate",
     "Mondo agricolo della Quarta Spirale, orbita la stella gialla Tuberalis. "
     "Tre lune: Bollita, Arrosto, Lessa. In lingua antica si chiama Solanum Magnum.",
     "pianeta,patate,quarta-spirale"),
    ("place", "Monte Buccia",
     "Unica vetta innevata del Pianeta Patate (4200 m). Sacra ai Tubrid. "
     "Sotto vi giace il Tempio del Solco.",
     "montagna,sacra"),
    ("place", "Mare del Brodo",
     "L'unico oceano del Pianeta Patate. Acqua dolce e tiepida. "
     "Ci vivono i Pesci Crocchetta.",
     "mare,oceano"),
    ("place", "Friggitorium",
     "Capitale del Pianeta Patate, ospita la Forgia delle Bucce, "
     "palazzo del sovrano.",
     "capitale,citta"),
    ("place", "Tempio del Solco",
     "Tempio sotterraneo sotto Monte Buccia. Si dice custodisca il "
     "Tubero Originale, il primo seme dei Tubrid.",
     "tempio,sacro,segreto"),
    ("place", "Abisso del Pelapatate",
     "Fossa oceanica del Pianeta Patate, profonda 11 km.",
     "abisso,oceano"),

    ("npc", "Re Patatone XII",
     "Sovrano attuale del Pianeta Patate, governa dalla Forgia delle Bucce a "
     "Friggitorium. Indossa un mantello rosso di radici intrecciate e una "
     "corona a forma di sale grosso. Ha ordinato un'inchiesta sui Crateri "
     "Cuocenti, ma nessun ricercatore è tornato.",
     "sovrano,re,inchiesta"),

    ("npc", "Tubrid",
     "Razza dominante del Pianeta Patate (i Tuberi Senzienti). Forma ovoidale, "
     "occhi multipli a germoglio, parlano il Solanico Antico. Filosofia: il "
     "Tuberismo, ogni essere contiene una scintilla nutriente da coltivare.",
     "razza,tuberi,senzienti"),

    ("event", "Guerra della Doppia Cottura",
     "Conflitto del 450 tra i Tubrid del Pianeta Patate e i Pomod'Oro, "
     "vegetali rivali del sistema solare Pasta Madre.",
     "guerra,storia,pomodori"),

    ("event", "Eclissi Olio",
     "Catastrofe astronomica del 1888 sul Pianeta Patate: le tre lune "
     "(Bollita, Arrosto, Lessa) si allinearono e il pianeta visse 70 giorni "
     "di buio bollente.",
     "catastrofe,eclissi,storia"),

    ("event", "Patto del Sale",
     "Alleanza eterna stipulata nel 1024 tra il Pianeta Patate e il regno "
     "di Friselonia.",
     "alleanza,trattato,storia"),

    ("event", "Festa della Frittura",
     "Festa principale dei Tubrid, celebrata ogni stagione di Arrosto. "
     "Dura tre giorni: ogni Tubrid intinge un germoglio in un calderone "
     "collettivo augurando buon raccolto.",
     "festa,tradizione"),

    ("item", "Tubero Originale",
     "Leggendario primo seme da cui sarebbero nati tutti i Tubrid. Custodito "
     "nel Tempio del Solco sotto Monte Buccia. Chi lo trova può parlare la "
     "lingua segreta dei vegetali.",
     "leggenda,artefatto,potere"),

    ("event", "Crateri Cuocenti",
     "Fenomeno recente sul Pianeta Patate: zone in cui la temperatura del "
     "terreno aumenta di 200°C senza causa apparente. Re Patatone XII ha "
     "ordinato un'inchiesta, ma i ricercatori inviati non sono mai tornati.",
     "mistero,attuale,pericolo"),

    ("note", "Tuberismo",
     "Filosofia centrale dei Tubrid del Pianeta Patate: ogni essere contiene "
     "una scintilla nutriente, e va coltivato con pazienza prima di essere "
     "'raccolto' (cioè completato come persona).",
     "filosofia,religione"),

    ("note", "Solanico Antico",
     "Lingua dei Tubrid del Pianeta Patate, in cui il pianeta stesso si "
     "chiama Solanum Magnum.",
     "lingua,antica"),
]


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = Database(DB_PATH)
    n = 0
    for kind, name, desc, tags in ENTRIES:
        db.add_lore(name=name, kind=kind, description=desc, tags=tags)
        n += 1
    print(f"Caricati {n} elementi di lore in {DB_PATH}")

    # Quick sanity check FTS
    print("\nTest ricerca: 'chi e re patatone?'")
    for r in db.search_lore("chi e re patatone"):
        print(" ->", r.to_context_line())

    print("\nTest ricerca: 'monte sacro tempio'")
    for r in db.search_lore("monte sacro tempio"):
        print(" ->", r.to_context_line())

    db.close()


if __name__ == "__main__":
    main()
