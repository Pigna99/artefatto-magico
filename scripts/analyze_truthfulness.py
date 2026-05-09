"""Analisi 'verita'' delle risposte dell'artefatto.

Per ogni turno utente nel DB:
1. Cerca quali lore/codex sarebbero stati matchati per quella query
2. Estrae i nomi propri (parole capitalizzate) dalla risposta dell'assistant
3. Per ogni nome proprio nella risposta, controlla se appartiene al matched lore
   o e' una parola comune (luna, sole, drago...) — quelli sono ok
4. Riporta i nomi 'sospetti' (capitalizzati, non in lore matched, non comuni)

Da lanciare sul Pi:
    /home/pigna/artefatto/.venv/bin/python scripts/analyze_truthfulness.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from db import Database

DB_PATH = Path.home() / "artefatto" / "data" / "artefatto.db"

# Pronomi/articoli/avverbi italiani che possono apparire capitalizzati a inizio
# frase. NON sono "nomi propri" e vanno ignorati.
ITALIAN_STOPWORDS = {
    # pronomi
    "Io", "Tu", "Egli", "Ella", "Lei", "Lui", "Noi", "Voi", "Essi", "Esse", "Loro",
    "Mi", "Ti", "Ci", "Vi", "Si", "Lo", "La", "Li", "Le", "Ne",
    "Mio", "Tuo", "Suo", "Nostro", "Vostro",
    "Questo", "Questa", "Questi", "Queste", "Quello", "Quella", "Quelli", "Quelle",
    "Chi", "Che", "Cui", "Cosa", "Quale", "Quali", "Tutto", "Tutti", "Ciascuno",
    "Ogni", "Alcuni", "Altri", "Tale", "Tali", "Tanto", "Tanti",
    # avverbi/congiunzioni
    "Sempre", "Mai", "Anche", "Ancora", "Forse", "Spesso", "Solo", "Pure",
    "Ma", "E", "Però", "Quindi", "Allora", "Dunque", "Perché", "Mentre",
    "Quando", "Come", "Dove", "Ecco", "Attualmente", "Inoltre",
    # verbi flessi comuni a inizio frase
    "Sono", "Siamo", "Siete", "Era", "Erano",
    "Ho", "Hai", "Ha", "Abbiamo", "Avete", "Hanno",
    "Fa", "Vai", "Vado", "Sii", "Sii",
    "Posso", "Puoi", "Può", "Possiamo", "Possono",
    "Devi", "Deve", "Dobbiamo", "Devono",
    "Vuoi", "Vuole", "Vogliamo", "Volete",
    "Ascolta", "Ascolto", "Senti",
    "Parla", "Dimmi", "Vedi", "Guarda",
    "Concentrati", "Utilizza", "Usa",
    "Spero", "Pensa", "Cerca", "Trova",
    "Si", "No",
}

# Parole capitalizzate "innocue" (italiano comune, narrativa generica)
COMMON_CAPITALIZED = {
    "Maestro", "Pigna", "Viandante", "Viandanti",
    "Sole", "Luna", "Stelle", "Cielo", "Terra", "Mare", "Mondo",
    "Nord", "Sud", "Est", "Ovest",
    "Re", "Regina", "Cavaliere", "Guerriero", "Mago", "Sacerdote",
    "Drago", "Lupo", "Aquila", "Serpente",
    "Dio", "Dei",
    "Italia", "Roma", "Firenze",  # toponimi reali ammessi
    "Ascolto", "Pace", "Forza", "Amore",
} | ITALIAN_STOPWORDS

# Match parole capitalizzate. Filtro a posteriori quelle dopo punteggiatura.
CAPITAL_RE = re.compile(r"\b([A-ZÀ-Ü][a-zà-ü']{2,})\b")
# Per identificare se una parola era a inizio frase (preceduta da .!?\n)
SENTENCE_START_RE = re.compile(r"(?:^|[.!?\n]\s*)([A-ZÀ-Ü][a-zà-ü']{2,})")


def extract_proper_nouns(text: str) -> set[str]:
    """Estrae nomi propri reali = capitalizzati che NON sono inizio frase."""
    all_caps = set(CAPITAL_RE.findall(text))
    sentence_starts = set(SENTENCE_START_RE.findall(text))
    # Un nome proprio è "vero" se appare ALMENO una volta NON a inizio frase,
    # oppure è in un context grafico (** **, _, ecc).
    # Heuristic semplice: rimuovo quelli che appaiono SOLO a inizio frase.
    real = set()
    for w in all_caps:
        # Conta apparizioni non a inizio frase
        non_start = re.findall(rf"(?<=[a-zà-ü,;\-\*\s]){re.escape(w)}\b", text)
        starts = sentence_starts
        if w in starts and not non_start:
            continue  # solo a inizio frase = probabilmente non è nome proprio
        real.add(w)
    return real


def load_lore_names(db: Database) -> set[str]:
    """Tutti i nomi propri presenti nel DB lore."""
    names = set()
    for entry in db.all_lore():
        names.add(entry.name)
        # Anche nomi multi-word ("Re Patatone XII") → spezza
        for w in CAPITAL_RE.findall(entry.name):
            names.add(w)
        # Estrai capitalizzate dalla description (così sappiamo che il lore le menziona)
        for w in CAPITAL_RE.findall(entry.description):
            names.add(w)
    return names


def load_codex_names(db: Database) -> set[str]:
    names = set()
    for entry in db.all_codex(limit=10000):
        for w in CAPITAL_RE.findall(entry.title + " " + entry.body):
            names.add(w)
    return names


def main():
    db = Database(DB_PATH)
    all_known = load_lore_names(db) | load_codex_names(db) | COMMON_CAPITALIZED

    # Prendo tutti i turni in ordine cronologico
    cur = db._conn.execute(
        "SELECT id, session_id, role, content, model, timestamp "
        "FROM messages ORDER BY id"
    )
    rows = list(cur.fetchall())

    print("=" * 76)
    print(f"DB: {DB_PATH}")
    print(f"Turni totali: {len(rows)}  ·  Lore noto: {len(all_known)} nomi")
    print("=" * 76)

    # Itera coppie (user, assistant) consecutive
    last_user = None
    issues_total = 0
    turns_analyzed = 0
    for r in rows:
        if r["role"] == "user":
            last_user = r["content"]
        elif r["role"] == "assistant" and last_user is not None:
            turns_analyzed += 1
            # Lore matchato per quella query
            matches = db.search_lore(last_user)
            matched_names = {m.name for m in matches}
            for m in matches:
                matched_names.update(CAPITAL_RE.findall(m.description))

            reply = r["content"]
            cap_in_reply = extract_proper_nouns(reply)
            # Nomi sospetti = capitalizzati non noti ovunque
            suspect = cap_in_reply - all_known
            # Nomi citati MA il lore non era stato matchato per quella query
            mentioned_unmatched = (cap_in_reply & all_known) - matched_names - COMMON_CAPITALIZED

            if suspect or mentioned_unmatched:
                print(f"\n--- turno @ {r['timestamp']} (modello {r['model']}) ---")
                print(f"   USER: {last_user[:120]}")
                print(f"   REPLY: {reply[:200]}")
                if matches:
                    print(f"   RAG ha matchato: {[m.name for m in matches]}")
                else:
                    print(f"   RAG: NESSUN MATCH (la risposta dovrebbe ammettere ignoranza)")
                if suspect:
                    print(f"   ⚠ inventati (capitalizzati ignoti): {sorted(suspect)}")
                    issues_total += len(suspect)
                if mentioned_unmatched:
                    print(f"   ℹ menzionati noti ma non matchati: {sorted(mentioned_unmatched)}")
            last_user = None  # consumato

    print("\n" + "=" * 76)
    print(f"Turni analizzati: {turns_analyzed}")
    print(f"Termini sospetti totali: {issues_total}")
    print("=" * 76)
    db.close()


if __name__ == "__main__":
    main()
