"""Test finale end-to-end di tutti i modelli (locale + turbo) sul lore
Pianeta Patate. Per ogni modello fa 1 warmup + 3 query RAG e raccoglie:
  - tempo totale, time-to-first-token, tokens/sec
  - presenza/numero di tag [LIGHT/BEEP/MOOD] nella risposta
  - lore matchato dal RAG (da Database.search_lore)
  - nomi propri citati nella risposta che NON sono nel lore noto (sospetti)

Output: full_test_results.md nella cwd.

Lancio sul Pi:
    /home/pigna/artefatto/.venv/bin/python scripts/full_test.py
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

import ollama  # type: ignore
from db import Database

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

DB_PATH = Path.home() / "artefatto" / "data" / "artefatto.db"
OUTPUT = HERE.parent / "full_test_results.md"

LOCAL_MODELS = ["gemma3:1b", "qwen3:0.6b", "gemma3:270m"]
TURBO_URL = os.environ.get("OLLAMA_TURBO_URL", "http://192.168.1.100:11434")
TURBO_MODELS = [
    "gemma4:latest", "qwen3:14b", "qwen3:8b",
    "gemma3:12b", "mistral-nemo:12b", "llama3.1:8b",
]

WARMUP = "Ciao, ci sei?"
QUERIES = [
    "Chi è Re Patatone XII e dove vive?",
    "Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?",
    "Cosa è successo durante l'Eclissi Olio?",
]

# Stesso system prompt della TUI (copiato per non importare textual)
SYSTEM_PROMPT = (
    "Sei un antico artefatto magico senziente che serve fedelmente Pigna. "
    "Tono solenne ma scopo = aiutare. In italiano, conciso. "
    "REGOLA DI VERITÀ: non inventare nomi, luoghi, eventi. Usa SOLO le informazioni "
    "del CONTESTO RILEVANTE che ti viene fornito. Se non c'è contesto, ammetti di non sapere. "
    "EFFETTI: puoi usare [LIGHT:colore:modo], [BEEP:tipo], [MOOD:atmosfera] nelle risposte; "
    "saranno eseguiti e rimossi prima del TTS."
)

# Regex tag
TAG_LIGHT = re.compile(r"\[LIGHT:[^\]]+\]", re.I)
TAG_BEEP = re.compile(r"\[BEEP:[^\]]+\]", re.I)
TAG_MOOD = re.compile(r"\[MOOD:[^\]]+\]", re.I)
CAPITAL_RE = re.compile(r"\b([A-ZÀ-Ü][a-zà-ü']{2,})\b")

STOPWORDS = {
    "Io","Tu","Lei","Lui","Noi","Voi","Loro","Si","No","Mio","Tuo","Suo",
    "Questo","Quella","Che","Chi","Cosa","Quale","Ogni","Tutto","Tutti",
    "Ma","E","Però","Quindi","Allora","Perché","Mentre","Quando","Come","Dove",
    "Sono","Era","Erano","Ho","Hai","Ha","Abbiamo","Hanno","Posso","Puoi","Può",
    "Pigna","Maestro","Viandante","Sole","Luna","Stelle","Cielo","Terra","Mondo",
    "Italia","Roma",
}


def load_known_names(db: Database) -> set[str]:
    names = set(STOPWORDS)
    for entry in db.all_lore():
        names.add(entry.name)
        for w in CAPITAL_RE.findall(entry.name + " " + entry.description):
            names.add(w)
    return names


def extract_proper_nouns(text: str) -> set[str]:
    """Capitalizzate dopo punteggiatura escluse."""
    all_caps = set(CAPITAL_RE.findall(text))
    # Rimuove quelle che appaiono solo dopo .!?\n (inizio frase)
    sentence_start = set()
    for m in re.finditer(r"(?:^|[.!?\n]\s*)([A-ZÀ-Ü][a-zà-ü']{2,})", text):
        sentence_start.add(m.group(1))
    return {w for w in all_caps
            if w not in sentence_start
            or re.search(rf"(?<=[a-zà-ü,;\-\*\s]){re.escape(w)}\b", text)}


def build_messages(query: str, db: Database):
    ctx = db.lore_context_for(query) + db.codex_context_for(query)
    base = [{"role": "system", "content": SYSTEM_PROMPT}]
    if ctx:
        base.append({"role": "system", "content": ctx.strip()})
    base.append({"role": "user", "content": query})
    return base, ctx


def run_one(client, model: str, query: str, db: Database, known_names: set[str]) -> dict:
    messages, ctx = build_messages(query, db)
    matched = [m.name for m in db.search_lore(query)]
    kwargs = {"model": model, "messages": messages, "stream": True}
    if "qwen3" in model.lower():
        kwargs["think"] = False

    t0 = time.perf_counter()
    t_first = None
    n_tok = 0
    text = ""
    try:
        for chunk in client.chat(**kwargs):
            tok = (chunk.get("message", {}) or {}).get("content", "") or ""
            if not tok:
                continue
            if t_first is None:
                t_first = time.perf_counter() - t0
            n_tok += 1
            text += tok
        ok = True
        err = ""
    except Exception as e:
        ok = False
        err = repr(e)
    total = time.perf_counter() - t0

    proper_nouns = extract_proper_nouns(text)
    suspect = sorted(proper_nouns - known_names)

    return {
        "model": model, "query": query, "ok": ok, "err": err,
        "total_s": total, "ttft_s": t_first or 0.0,
        "tokens": n_tok, "tps": n_tok / total if total > 0 else 0.0,
        "rag_matched": matched,
        "rag_used_in_text": any(m.lower() in text.lower() for m in matched),
        "tags_light": len(TAG_LIGHT.findall(text)),
        "tags_beep": len(TAG_BEEP.findall(text)),
        "tags_mood": len(TAG_MOOD.findall(text)),
        "suspect": suspect,
        "text": text.strip(),
    }


def test_model(client, model: str, db: Database, known_names: set[str], lines: list):
    print(f"\n=== {model} ===")
    print(f"  warmup...")
    try:
        client.chat(model=model, messages=[{"role": "user", "content": WARMUP}],
                    stream=False)
    except Exception as e:
        print(f"  warmup FALLITO: {e}")
        lines.append(f"\n### {model}\n\n**ERRORE warmup**: `{e}`\n")
        return

    results = []
    for q in QUERIES:
        print(f"  query: {q[:50]}...")
        r = run_one(client, model, q, db, known_names)
        if r["ok"]:
            print(f"    -> {r['total_s']:.1f}s · {r['tokens']} tok · "
                  f"{r['tps']:.1f} tps · RAG used={r['rag_used_in_text']} · "
                  f"tags(L/B/M)={r['tags_light']}/{r['tags_beep']}/{r['tags_mood']} · "
                  f"sospetti={len(r['suspect'])}")
        else:
            print(f"    -> ERRORE: {r['err']}")
        results.append(r)

    # Render markdown per questo modello
    lines.append(f"\n### {model}\n")
    lines.append("| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    avg_total = avg_tps = 0.0
    n_ok = 0
    for i, r in enumerate(results, 1):
        if not r["ok"]:
            lines.append(f"| {i} | {r['query'][:40]} | — | — | — | — | — | — | — | ERR: {r['err'][:50]} |")
            continue
        avg_total += r["total_s"]
        avg_tps += r["tps"]
        n_ok += 1
        susp = ", ".join(r["suspect"][:5]) or "—"
        matched_str = ", ".join(r["rag_matched"][:3]) or "—"
        lines.append(
            f"| {i} | {r['query'][:40]} | {r['total_s']:.1f}s | "
            f"{r['ttft_s']:.1f}s | {r['tokens']} | {r['tps']:.1f} | "
            f"{matched_str} | {'✓' if r['rag_used_in_text'] else '✗'} | "
            f"{r['tags_light']}/{r['tags_beep']}/{r['tags_mood']} | {susp} |"
        )
    if n_ok > 0:
        lines.append(f"\n**Medie**: {avg_total/n_ok:.1f}s totali, {avg_tps/n_ok:.1f} tps\n")

    # Risposte testuali integrali per giudizio qualitativo
    lines.append("\n<details><summary>Risposte integrali</summary>\n")
    for i, r in enumerate(results, 1):
        if r["ok"]:
            lines.append(f"\n**Q{i}**: {r['query']}\n\n```\n{r['text']}\n```\n")
    lines.append("</details>\n")


def main():
    db = Database(DB_PATH)
    known_names = load_known_names(db)
    print(f"DB: {DB_PATH}  ·  nomi noti: {len(known_names)}")

    lines = [
        "# Full test — modelli locali + turbo\n",
        f"DB: `{DB_PATH}`  ·  nomi lore noti: {len(known_names)}  ·  "
        f"data: {time.strftime('%Y-%m-%d %H:%M')}\n",
        f"\nQueries:\n",
    ]
    for q in QUERIES:
        lines.append(f"- {q}")
    lines.append("\n## Modalità LOCALE (Pi)\n")

    local = ollama.Client()
    for m in LOCAL_MODELS:
        test_model(local, m, db, known_names, lines)

    lines.append("\n## Modalità TURBO (PC RX 6800)\n")
    try:
        turbo = ollama.Client(host=TURBO_URL)
        # Probe connessione
        turbo.list()
    except Exception as e:
        lines.append(f"\n**Turbo non raggiungibile** ({TURBO_URL}): `{e}`\n")
        turbo = None

    if turbo is not None:
        for m in TURBO_MODELS:
            test_model(turbo, m, db, known_names, lines)

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n✓ Risultati in {OUTPUT}")
    db.close()


if __name__ == "__main__":
    main()
