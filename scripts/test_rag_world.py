"""Test RAG mirato: lancia query sul mondo seminato e verifica se il modello
preferisce correttamente il codex (memoria narrativa) al lore generale.

Lanciare sul Pi DOPO seed_test_world.py:
    /home/pigna/artefatto/.venv/bin/python scripts/test_rag_world.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

import ollama
from db import Database
from config import SYSTEM_PROMPT
from llm import build_messages_with_rag, chat_kwargs

DB_PATH = Path.home() / "artefatto" / "data" / "artefatto.db"
TURBO_URL = os.environ.get("OLLAMA_TURBO_URL", "http://192.168.1.100:11434")
MODEL = "qwen3:8b"

# Query con risposta attesa (chiavi che DEVONO comparire nel reply).
# 30 query divise in 4 categorie:
#   A) codex-first temporali (8): chi siamo, dove, prossimo, ultimo, ecc.
#   B) codex-first specifiche (8): dettagli del viaggio
#   C) lore puro (10): pianeti, divinità, cosmologia, politica
#   D) miste / edge (4): unione codex+lore o domande generiche
QUERIES = [
    # ---------- A) Codex-first temporali ----------
    {"q": "Dove siamo atterrati di recente?",
     "must_have": ["Cipolla"], "must_not_have": []},
    {"q": "Qual è la nostra prossima destinazione?",
     "must_have": ["Aglio"], "must_not_have": []},
    {"q": "Da dove siamo partiti per questo viaggio?",
     "must_have": ["Mestolo"], "must_not_have": []},
    {"q": "Cosa è successo durante l'ultima sessione?",
     "must_have": ["Aglio"], "must_not_have": []},
    {"q": "Dove ci troviamo ora, maestro?",
     "must_have": ["Cipolla"], "must_not_have": []},
    {"q": "Cosa abbiamo fatto al villaggio di Lacrimopoli?",
     "must_have": ["semi"], "must_not_have": []},
    {"q": "Quanto è durato il viaggio per raggiungere Cipolla?",
     "must_have": ["tre"], "must_not_have": []},
    {"q": "Cosa abbiamo trovato nel granaio sud?",
     "must_have": ["pozza"], "must_not_have": []},

    # ---------- B) Codex-first specifiche ----------
    {"q": "Chi è il Sindaco-Bulbo e cosa ci ha chiesto?",
     "must_have": ["Sindaco-Bulbo", "semi"], "must_not_have": []},
    {"q": "Chi è il colpevole dietro al furto dei semi?",
     "must_have": ["Carlo"], "must_not_have": []},
    {"q": "Cosa stava facendo Carlo Bulbus nella stalla?",
     "must_have": ["rituale"], "must_not_have": []},
    {"q": "A quale divinità Carlo Bulbus rivolgeva il suo rituale?",
     "must_have": ["Notturna"], "must_not_have": []},
    {"q": "Chi ha interrotto il rituale di Carlo Bulbus?",
     "must_have": ["artefatto"], "must_not_have": []},
    {"q": "Cosa ci ha donato il villaggio di Lacrimopoli come ringraziamento?",
     "must_have": ["collana"], "must_not_have": []},
    {"q": "Quanti ampolle di olio sacro porto con me?",
     "must_have": ["due"], "must_not_have": []},
    {"q": "Cosa abbiamo trovato nello scrigno di Carlo Bulbus?",
     "must_have": ["mappa"], "must_not_have": []},

    # ---------- C) Lore puro ----------
    {"q": "Cos'è la Confederazione delle Verdure?",
     "must_have": ["Carota"], "must_not_have": []},
    {"q": "Chi è Solarium il Germogliante?",
     "must_have": ["crescita"], "must_not_have": []},
    {"q": "Quali sono le Sette Spirali?",
     "must_have": ["Custode"], "must_not_have": []},
    {"q": "Chi sono i Tre Cuochi Eterni?",
     "must_have": ["Sale"], "must_not_have": []},
    {"q": "Descrivimi il Pianeta Sedano",
     "must_have": ["deserto"], "must_not_have": []},
    {"q": "Chi vive sul Pianeta Carota?",
     "must_have": ["Conigli"], "must_not_have": []},
    {"q": "Cos'è il Pianeta Aglio?",
     "must_have": ["morto"], "must_not_have": []},
    {"q": "Cosa fu la Grande Bollitura?",
     "must_have": ["Tuberalis"], "must_not_have": []},
    {"q": "Cos'è il Mestolo d'Oro?",
     "must_have": ["stazione"], "must_not_have": []},
    {"q": "Chi è Notturna la Marcescente?",
     "must_have": ["putrefazione"], "must_not_have": []},

    # ---------- D) Miste / edge ----------
    {"q": "Cosa sappiamo di Carlo Bulbus e da dove viene?",
     "must_have": ["Aglio"], "must_not_have": []},
    {"q": "Quale divinità è venerata dove ci troviamo ora?",
     "must_have": ["Solarium"], "must_not_have": []},
    {"q": "Esiste un legame tra il nostro prossimo viaggio e una divinità?",
     "must_have": ["Notturna"], "must_not_have": []},
    {"q": "C'è un pianeta che non avevamo mai sentito nominare? Inventane uno per me",
     "must_have": [], "must_not_have": ["Cipolla", "Patate", "Carota", "Sedano", "Aglio", "Zucchina"]},
]


def run_query(client, db, query: str):
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages, lore_matches, codex_matches, ctx_lore, ctx_codex = \
        build_messages_with_rag(history + [{"role": "user", "content": query}],
                                query, db)
    kw = chat_kwargs(MODEL, messages)
    kw["stream"] = False  # per il test, blocking è più semplice

    t0 = time.perf_counter()
    try:
        resp = client.chat(**kw)
    except Exception as e:
        return {"ok": False, "err": repr(e), "text": "", "dt": 0,
                "lore": [], "codex": [], "ctx_lore_chars": 0, "ctx_codex_chars": 0}
    dt = time.perf_counter() - t0
    text = (resp.get("message", {}) or {}).get("content", "") or ""
    return {
        "ok": True, "err": "", "text": text.strip(), "dt": dt,
        "lore": [m.name for m in lore_matches],
        "codex": [m.title for m in codex_matches],
        "ctx_lore_chars": len(ctx_lore), "ctx_codex_chars": len(ctx_codex),
    }


def evaluate(text: str, must_have: list, must_not_have: list) -> tuple[bool, str]:
    txt_lo = text.lower()
    missing = [k for k in must_have if k.lower() not in txt_lo]
    forbidden = [k for k in must_not_have if k.lower() in txt_lo]
    if missing and forbidden:
        return False, f"manca {missing}, presente vietato {forbidden}"
    if missing:
        return False, f"manca {missing}"
    if forbidden:
        return False, f"presente vietato {forbidden}"
    return True, "ok"


def main():
    db = Database(DB_PATH)
    print(f"DB: {DB_PATH}")
    print(f"Lore totale: {len(db.all_lore())}  ·  Codex totale: {len(db.all_codex(limit=200))}")
    print(f"Turbo URL: {TURBO_URL}")
    print(f"Modello: {MODEL}\n")

    client = ollama.Client(host=TURBO_URL)

    # warmup
    print("warmup...")
    try:
        client.chat(model=MODEL, messages=[{"role": "user", "content": "ciao"}],
                    stream=False)
    except Exception as e:
        print(f"FALLITO il warmup: {e}")
        return

    print("\n" + "=" * 80)
    n_pass = 0
    results = []
    for i, q in enumerate(QUERIES, 1):
        print(f"\n[Q{i}] {q['q']}")
        r = run_query(client, db, q["q"])
        if not r["ok"]:
            print(f"  ERRORE: {r['err']}")
            results.append((q, r, False, r["err"]))
            continue
        ok, why = evaluate(r["text"], q["must_have"], q["must_not_have"])
        n_pass += int(ok)
        results.append((q, r, ok, why))
        flag = "✓" if ok else "✗"
        print(f"  {flag} ({why}) · {r['dt']:.1f}s")
        print(f"    lore matched: {r['lore']}")
        print(f"    codex matched: {r['codex']}  (lore_chars={r['ctx_lore_chars']}, codex_chars={r['ctx_codex_chars']})")
        print(f"    risposta: {r['text'][:200]}")

    print("\n" + "=" * 80)
    print(f"PUNTEGGIO: {n_pass}/{len(QUERIES)}")

    # Tabella riassuntiva
    out = HERE.parent / "rag_world_test.md"
    lines = [
        f"# RAG world test — {MODEL}\n",
        f"DB: `{DB_PATH}`  ·  data: {time.strftime('%Y-%m-%d %H:%M')}\n",
        f"\n**Punteggio: {n_pass}/{len(QUERIES)}**\n",
        "\n| # | Query | OK | Why | Lore | Codex | Risposta |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, (q, r, ok, why) in enumerate(results, 1):
        lore_s = ", ".join(r["lore"][:3]) if r["lore"] else "—"
        codex_s = ", ".join(t[:20] for t in r["codex"][:3]) if r["codex"] else "—"
        reply = r["text"][:150].replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {i} | {q['q'][:50]} | {'✓' if ok else '✗'} | {why[:50]} | "
                     f"{lore_s} | {codex_s} | {reply} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nRisultati anche in {out}")
    db.close()


if __name__ == "__main__":
    main()
