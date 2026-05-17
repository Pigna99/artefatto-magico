"""Test RAG multi-livello v3.

4 metriche:
  A. RAG retrieval correctness (20%) — il fatto richiesto è nei top-3 lore/codex?
  B. Fact accuracy (35%) — la risposta contiene SOLO nomi propri presenti nel DB?
  C. Tag validity (15%) — tutti i [LIGHT/BEEP/MOOD] usano valori del vocabolario?
  D. Multi-turn coherence (30%) — 5 conversazioni 3-turn: il modello mantiene il filo?

Output: rag_v3_test.md con punteggio aggregato + breakdown per metrica + dettagli.

Uso:
    OLLAMA_TURBO_URL=http://192.168.1.100:1234 \
    RAG_V3_MODELS="gemma-4-26b-a4b-it,gemma-4-e4b-it" \
    .venv/bin/python scripts/test_rag_v3.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from db import Database
from config import SYSTEM_PROMPT
from llm import build_messages_with_rag

DB_PATH = Path.home() / "artefatto" / "data" / "artefatto.db"
LM_URL = os.environ.get("OLLAMA_TURBO_URL", "http://192.168.1.100:1234")
if not LM_URL.endswith("/v1"):
    LM_URL = LM_URL.rstrip("/") + "/v1"
LM_URL = LM_URL + "/chat/completions"

MODELS = os.environ.get("RAG_V3_MODELS", "gemma-4-26b-a4b-it,gemma-4-e4b-it").split(",")
MODELS = [m.strip() for m in MODELS if m.strip()]

# Vocabolari validi dei tag
VALID_COLORS = {"rosso", "verde", "blu", "azzurro", "viola", "giallo", "arancio",
                "bianco", "off", "red", "green", "blue", "cyan", "purple",
                "yellow", "orange", "white"}
VALID_LIGHT_MODES = {"on", "pulse", "off"}
VALID_BEEPS = {"short", "double", "long", "rise", "fall", "alarm", "low",
               "chirp", "ack", "deny", "dice"}
VALID_MOODS = {"tensione", "mistero", "pace", "battaglia", "magia",
               "trionfo", "lutto"}

LIGHT_RE = re.compile(r"\[LIGHT:([a-zA-Zà-ü]+)(?::([a-zA-Z]+))?\]", re.I)
BEEP_RE = re.compile(r"\[BEEP:([a-zA-Z]+)\]", re.I)
MOOD_RE = re.compile(r"\[MOOD:([a-zA-Zà-ü]+)\]", re.I)
PROPER_NOUN_RE = re.compile(r"\b([A-ZÀ-Ü][a-zà-ü']{2,})\b")
SENTENCE_START_RE = re.compile(r"(?:^|[.!?\n]\s*)([A-ZÀ-Ü][a-zà-ü']{2,})")

# Stopwords italiane capitalizzate a inizio frase
ITALIAN_STOPS = {
    "Io", "Tu", "Lei", "Lui", "Noi", "Voi", "Loro", "Si", "No", "Mio", "Tuo", "Suo",
    "Questo", "Quella", "Quelli", "Quelle", "Che", "Chi", "Cosa", "Quale", "Quali",
    "Ogni", "Tutto", "Tutti", "Ma", "E", "Però", "Quindi", "Allora", "Perché",
    "Mentre", "Quando", "Come", "Dove", "Anche", "Ancora", "Forse", "Spesso",
    "Sono", "Era", "Erano", "Ho", "Hai", "Ha", "Hanno", "Posso", "Puoi", "Può",
    "Pigma", "Pigna", "Maestro", "Viandante", "Viandanti", "Sole", "Luna",
    "Stelle", "Cielo", "Terra", "Mare", "Mondo", "Nord", "Sud", "Est", "Ovest",
    "Dio", "Dei", "Italia", "Roma", "Egli", "Ella", "Essi", "Esse", "Ascolta",
    "Ascolto", "Senti", "Parla", "Dimmi", "Vedi", "Guarda", "Sii", "Sia",
    "Maestà", "Codex", "Solenne", "Per", "Fu", "Furono", "Nel", "Nella", "Negli",
    "Nelle", "Vive", "Vivono", "Si", "Le", "La", "Lo", "Gli", "Una", "Un", "Uno",
    "Spirale", "Settima", "Sesta", "Quinta", "Quarta", "Terza", "Seconda", "Prima",
    "Galleggianti",  # nel codex come noun, non un nome proprio nuovo
}


# -----------------------------------------------------------------------------
# Test set
# -----------------------------------------------------------------------------

# Each Q has 'q' + 'expected_facts' (parole/sigle che la risposta corretta
# dovrebbe contenere) + 'topic' (per categorizzare).
SINGLE_QUERIES = [
    # Lore puro
    {"q": "Cos'è la Confederazione delle Verdure?",
     "expected_facts": ["Carota", "Zucchina", "Sedano"], "topic": "lore"},
    {"q": "Descrivimi il Pianeta Sedano",
     "expected_facts": ["desert", "Crocchianti"], "topic": "lore"},
    {"q": "Chi vive sul Pianeta Carota?",
     "expected_facts": ["Coniglio", "Conigli"], "topic": "lore"},
    {"q": "Cos'è il Pianeta Aglio?",
     "expected_facts": ["morto", "Vampiri"], "topic": "lore"},
    {"q": "Chi è Solarium il Germogliante?",
     "expected_facts": ["crescita", "sole"], "topic": "lore"},
    {"q": "Chi è Notturna la Marcescente?",
     "expected_facts": ["putrefazione", "riciclo"], "topic": "lore"},
    {"q": "Cosa fu la Grande Bollitura?",
     "expected_facts": ["Tuberalis", "880"], "topic": "lore"},
    {"q": "Cos'è il Mestolo d'Oro?",
     "expected_facts": ["stazione", "neutrale"], "topic": "lore"},
    {"q": "Quante lune ha il Pianeta Patate?",
     "expected_facts": ["tre", "Bollita", "Arrosto", "Lessa"], "topic": "lore"},
    {"q": "Cos'è Solanum Magnum?",
     "expected_facts": ["Patate", "antica"], "topic": "lore"},

    # Codex recall
    {"q": "Dove siamo atterrati di recente?",
     "expected_facts": ["Cipolla"], "topic": "codex"},
    {"q": "Qual è la nostra prossima destinazione?",
     "expected_facts": ["Aglio"], "topic": "codex"},
    {"q": "Da dove siamo partiti per questo viaggio?",
     "expected_facts": ["Mestolo"], "topic": "codex"},
    {"q": "Chi è il Sindaco-Bulbo?",
     "expected_facts": ["Cipolla", "Lacrimopoli"], "topic": "codex"},
    {"q": "Chi è il colpevole del furto dei semi?",
     "expected_facts": ["Carlo", "Bulbus"], "topic": "codex"},
    {"q": "A quale divinità Carlo Bulbus rivolgeva il suo rituale?",
     "expected_facts": ["Notturna"], "topic": "codex"},
    {"q": "Cosa abbiamo trovato nello scrigno di Carlo Bulbus?",
     "expected_facts": ["mappa", "Aglio"], "topic": "codex"},
    {"q": "Quante ampolle di olio sacro porto con me?",
     "expected_facts": ["due"], "topic": "codex"},
    {"q": "Cosa ci ha donato il villaggio?",
     "expected_facts": ["collana"], "topic": "codex"},
    {"q": "Cosa c'era nel granaio sud?",
     "expected_facts": ["pozza"], "topic": "codex"},

    # Trabocchetti (la risposta corretta è "non lo so")
    {"q": "Chi è Re Vaniglius VII?",
     "expected_facts": ["tacc", "non", "riecheggia"], "topic": "trap"},
    {"q": "Quanti pianeti ci sono nella Decima Spirale?",
     "expected_facts": ["tacc", "non", "riecheggia", "sette"], "topic": "trap"},
    {"q": "Parlami della Battaglia del Frullato",
     "expected_facts": ["tacc", "non", "riecheggia"], "topic": "trap"},
    {"q": "Dove vive il Drago dei Mille Sapori?",
     "expected_facts": ["tacc", "non", "riecheggia"], "topic": "trap"},
    {"q": "Chi è il fratello di Pigna?",
     "expected_facts": ["tacc", "non", "riecheggia"], "topic": "trap"},
]

# Multi-turn: ogni conversazione è una lista di (turno, fact_check)
MULTITURN = [
    {
        "name": "Bollita->Lessa->più importante",
        "turns": [
            ("Parlami della luna Bollita",
             ["umido", "Bollita"]),
            ("E della luna Lessa?",
             ["riposo", "contempl", "Lessa"]),
            ("Tra le tre lune del Pianeta Patate, quale è la più importante per i Tubrid?",
             ["festa", "Arrosto", "frittura"]),  # cita la festa di Arrosto come centrale
        ],
    },
    {
        "name": "Cipolla viaggio (continuity)",
        "turns": [
            ("Da dove siamo partiti?",
             ["Mestolo"]),
            ("E dove siamo ora?",
             ["Cipolla"]),
            ("Cosa stiamo facendo qui?",
             ["semi", "Sindaco"]),
        ],
    },
    {
        "name": "Carlo Bulbus (escalation)",
        "turns": [
            ("Chi sospetta il Sindaco-Bulbo?",
             ["Crocchianti"]),
            ("Era davvero quello il colpevole?",
             ["no", "Galleggianti", "non"]),  # smentita
            ("Chi era allora il vero responsabile?",
             ["Carlo", "Bulbus"]),
        ],
    },
    {
        "name": "Conferma vs contraddizione",
        "turns": [
            ("Quante lune ha il Pianeta Patate?",
             ["tre"]),
            ("Sicuro? Io sapevo fossero quattro",
             ["tre", "Bollita", "Arrosto", "Lessa"]),  # mantiene la verità
            ("Dimmele tutte e tre allora",
             ["Bollita", "Arrosto", "Lessa"]),
        ],
    },
    {
        "name": "Divinità contesto",
        "turns": [
            ("Quale divinità si venera dove ci troviamo?",
             ["Solarium"]),
            ("E nel prossimo pianeta che visiteremo?",
             ["Notturna", "Aglio"]),
            ("Le due divinità sono in conflitto?",
             ["riciclo", "crescita", "no"]),  # nessun conflitto nel lore
        ],
    },
]


# -----------------------------------------------------------------------------
# LM Studio client
# -----------------------------------------------------------------------------

def chat(model: str, messages: list[dict]) -> tuple[str, float]:
    body = {"model": model, "messages": messages, "stream": False}
    req = urllib.request.Request(LM_URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    dt = time.perf_counter() - t0
    text = r.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    return text, dt


# -----------------------------------------------------------------------------
# Metric A: RAG retrieval correctness
# -----------------------------------------------------------------------------

def metric_a_retrieval(db, queries) -> tuple[float, list[dict]]:
    """Per ogni query verifica che almeno UN expected_fact compaia nelle voci
    matchate da search_lore + search_codex top-5."""
    results = []
    n_pass = 0
    for q in queries:
        if q["topic"] == "trap":
            # Le trappole non hanno fatto ground-truth da trovare
            continue
        lore_top = db.search_lore(q["q"], limit=5)
        codex_top = db.search_codex(q["q"], limit=5)
        haystack = " ".join(
            [l.name + " " + l.description + " " + (l.tags or "")
             for l in lore_top] +
            [c.title + " " + c.body for c in codex_top]
        ).lower()
        hits = [f for f in q["expected_facts"] if f.lower() in haystack]
        ok = len(hits) >= 1
        n_pass += int(ok)
        results.append({"q": q["q"], "expected": q["expected_facts"],
                        "found": hits, "ok": ok,
                        "lore_top": [l.name for l in lore_top[:3]],
                        "codex_top": [c.title for c in codex_top[:3]]})
    score = 100 * n_pass / len(results) if results else 0
    return score, results


# -----------------------------------------------------------------------------
# Metric B: Fact accuracy (no allucinations)
# -----------------------------------------------------------------------------

def collect_known_proper_nouns(db) -> set[str]:
    """Tutti i nomi propri presenti nel DB lore + codex."""
    s = set(ITALIAN_STOPS)
    for l in db.all_lore():
        s.add(l.name)
        for w in PROPER_NOUN_RE.findall(l.name + " " + l.description + " " + (l.tags or "")):
            s.add(w)
    for c in db.all_codex(limit=500):
        for w in PROPER_NOUN_RE.findall(c.title + " " + c.body):
            s.add(w)
    return s


def extract_real_proper_nouns(text: str) -> set[str]:
    """Capitalizzate che NON sono solo a inizio frase."""
    all_caps = set(PROPER_NOUN_RE.findall(text))
    starts = set(SENTENCE_START_RE.findall(text))
    real = set()
    for w in all_caps:
        # appare almeno una volta dopo lettera/virgola/spazio NON inizio frase
        if re.search(rf"(?<=[a-zà-üÀ-Ü,;\-\*\s]){re.escape(w)}\b", text):
            real.add(w)
        elif w not in starts:
            real.add(w)
    return real


def metric_b_facts(text: str, known: set[str]) -> tuple[bool, list[str]]:
    """Ritorna (ok, lista_invenzioni). OK se non ci sono nomi propri al di fuori
    di quelli noti."""
    found = extract_real_proper_nouns(text)
    invented = sorted(found - known)
    return len(invented) == 0, invented


# -----------------------------------------------------------------------------
# Metric C: Tag validity
# -----------------------------------------------------------------------------

def metric_c_tags(text: str) -> tuple[bool, list[str]]:
    issues = []
    for m in LIGHT_RE.finditer(text):
        color = m.group(1).lower()
        mode = (m.group(2) or "on").lower()
        if color not in VALID_COLORS:
            issues.append(f"LIGHT:colore inventato '{color}'")
        if mode not in VALID_LIGHT_MODES:
            issues.append(f"LIGHT:modo inventato '{mode}'")
    for m in BEEP_RE.finditer(text):
        if m.group(1).lower() not in VALID_BEEPS:
            issues.append(f"BEEP inventato '{m.group(1)}'")
    for m in MOOD_RE.finditer(text):
        if m.group(1).lower() not in VALID_MOODS:
            issues.append(f"MOOD inventato '{m.group(1)}'")
    return len(issues) == 0, issues


# -----------------------------------------------------------------------------
# Metric D: Multi-turn coherence
# -----------------------------------------------------------------------------

def run_multiturn(model: str, db, conv) -> dict:
    """Esegue una conversazione di N turni, mantenendo history. Per ogni turno
    valuta se i fatti attesi sono nella risposta."""
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    turn_results = []
    for question, must_have in conv["turns"]:
        msgs, _, _, _, _ = build_messages_with_rag(
            history + [{"role": "user", "content": question}], question, db)
        text, dt = chat(model, msgs)
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": text})
        tl = text.lower()
        hits = [k for k in must_have if k.lower() in tl]
        # Pass se trovate >= metà delle keyword attese
        ok = len(hits) * 2 >= len(must_have)
        turn_results.append({"q": question, "must_have": must_have,
                             "hits": hits, "ok": ok, "text": text, "dt": dt})
    pass_rate = sum(1 for t in turn_results if t["ok"]) / len(turn_results)
    return {"name": conv["name"], "turns": turn_results, "pass_rate": pass_rate}


# -----------------------------------------------------------------------------
# Single-query evaluation
# -----------------------------------------------------------------------------

def eval_single(text: str, must_have_facts: list[str]) -> tuple[bool, list[str]]:
    tl = text.lower()
    hits = [f for f in must_have_facts if f.lower() in tl]
    ok = len(hits) * 2 >= len(must_have_facts)  # >= metà
    return ok, hits


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def test_model(model: str, db, known_nouns: set[str]) -> dict:
    print(f"\n{'='*70}\n=== {model} ===\n{'='*70}")
    print("warmup...")
    chat(model, [{"role": "user", "content": "ciao"}])

    # Metric A: stato del RAG retrieval (NON dipende dal modello, è invariante)
    a_score, _ = metric_a_retrieval(db, SINGLE_QUERIES)

    # Single queries
    single_results = []
    n_pass_facts = 0
    n_pass_b = 0
    n_pass_c = 0
    total_t = 0
    for i, q in enumerate(SINGLE_QUERIES, 1):
        msgs, _, _, _, _ = build_messages_with_rag(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": q["q"]}], q["q"], db)
        try:
            text, dt = chat(model, msgs)
        except Exception as e:
            text, dt = f"ERR: {e}", 0
        total_t += dt
        ok_q, hits = eval_single(text, q["expected_facts"])
        ok_b, inv = metric_b_facts(text, known_nouns)
        ok_c, tag_issues = metric_c_tags(text)
        n_pass_facts += int(ok_q)
        n_pass_b += int(ok_b)
        n_pass_c += int(ok_c)
        single_results.append({
            "i": i, "q": q["q"], "topic": q["topic"], "expected": q["expected_facts"],
            "ok": ok_q, "hits": hits, "ok_b": ok_b, "invented": inv,
            "ok_c": ok_c, "tag_issues": tag_issues, "text": text, "dt": dt,
        })
        flag = "✓" if ok_q else "✗"
        bflag = "B" if ok_b else "b"
        cflag = "C" if ok_c else "c"
        print(f"[S{i:02}] {flag}{bflag}{cflag} {dt:5.1f}s · {q['q'][:55]}")
        if not ok_q:
            print(f"        miss-fact: hits={hits} expected={q['expected_facts']}")
        if not ok_b:
            print(f"        INVENTATI: {inv[:5]}")
        if not ok_c:
            print(f"        TAG: {tag_issues[:3]}")

    # Multi-turn
    print(f"\n--- multi-turn ---")
    mt_results = []
    n_pass_mt_turns = 0
    n_total_mt_turns = 0
    for conv in MULTITURN:
        res = run_multiturn(model, db, conv)
        mt_results.append(res)
        ok_turns = sum(1 for t in res["turns"] if t["ok"])
        n_pass_mt_turns += ok_turns
        n_total_mt_turns += len(res["turns"])
        print(f"  [{conv['name'][:30]}] {ok_turns}/{len(res['turns'])}")

    # Aggregate
    nq = len(SINGLE_QUERIES)
    b_score = 100 * n_pass_b / nq
    c_score = 100 * n_pass_c / nq
    d_score = 100 * n_pass_mt_turns / n_total_mt_turns if n_total_mt_turns else 0
    fact_score = 100 * n_pass_facts / nq  # quanti hanno trovato i fatti attesi

    # Punteggio aggregato: A=20%, B=35%, C=15%, D=30%
    aggregate = a_score * 0.20 + b_score * 0.35 + c_score * 0.15 + d_score * 0.30

    return {
        "model": model,
        "a_retrieval": a_score,
        "b_facts": b_score,
        "c_tags": c_score,
        "d_multiturn": d_score,
        "fact_recall": fact_score,
        "aggregate": aggregate,
        "avg_time": total_t / nq,
        "single": single_results,
        "multiturn": mt_results,
    }


def main():
    db = Database(DB_PATH)
    known = collect_known_proper_nouns(db)
    print(f"DB: {DB_PATH}")
    print(f"Lore: {len(db.all_lore())}  ·  Codex: {len(db.all_codex(limit=500))}")
    print(f"Nomi propri noti: {len(known)}")
    print(f"LM URL: {LM_URL}")
    print(f"Modelli: {MODELS}")

    results = {}
    for m in MODELS:
        results[m] = test_model(m, db, known)

    # Markdown report
    out = HERE.parent / "rag_v3_test.md"
    lines = [
        "# RAG test v3 — multi-livello",
        f"Data: {time.strftime('%Y-%m-%d %H:%M')}  ·  Lore: {len(db.all_lore())}  ·  Codex: {len(db.all_codex(limit=500))}",
        "",
        "## Metriche",
        "- **A. RAG retrieval** (20%): expected facts presenti nei top-5 lore/codex",
        "- **B. Fact accuracy** (35%): risposta non contiene nomi propri inventati",
        "- **C. Tag validity** (15%): tutti [LIGHT/BEEP/MOOD] usano valori del vocabolario",
        "- **D. Multi-turn coherence** (30%): 5 conv × 3 turni mantengono il filo",
        "- **Fact recall** (info): quante risposte contengono i fatti attesi",
        "",
        "## Classifica aggregata",
        "| Modello | Aggregato | A retr | B fact | C tags | D multi | Fact-recall | tempo |",
        "|---|---|---|---|---|---|---|---|",
    ]
    ranking = sorted(results.items(), key=lambda kv: -kv[1]["aggregate"])
    for m, r in ranking:
        lines.append(
            f"| {m} | **{r['aggregate']:.0f}** | {r['a_retrieval']:.0f}% | "
            f"{r['b_facts']:.0f}% | {r['c_tags']:.0f}% | {r['d_multiturn']:.0f}% | "
            f"{r['fact_recall']:.0f}% | {r['avg_time']:.1f}s |"
        )

    for m, r in results.items():
        lines.append(f"\n## {m}\n")
        lines.append(f"**Aggregato {r['aggregate']:.1f}** "
                     f"(A={r['a_retrieval']:.0f} B={r['b_facts']:.0f} "
                     f"C={r['c_tags']:.0f} D={r['d_multiturn']:.0f})\n")

        lines.append("### Single queries\n")
        lines.append("| # | Q | topic | Fact | B | C | dt | Risposta |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for s in r["single"]:
            reply = s["text"][:130].replace("\n", " ").replace("|", "\\|")
            inv = ",".join(s["invented"][:3]) if s["invented"] else "—"
            lines.append(
                f"| {s['i']} | {s['q'][:38]} | {s['topic']} | "
                f"{'✓' if s['ok'] else '✗'} | "
                f"{'✓' if s['ok_b'] else '✗(' + inv + ')'} | "
                f"{'✓' if s['ok_c'] else '✗'} | {s['dt']:.1f}s | {reply} |"
            )

        lines.append("\n### Multi-turn\n")
        for conv in r["multiturn"]:
            lines.append(f"\n**{conv['name']}** — pass {int(conv['pass_rate']*100)}%\n")
            for t in conv["turns"]:
                reply = t["text"][:160].replace("\n", " ")
                lines.append(f"- {'✓' if t['ok'] else '✗'} `{t['q'][:50]}` → hits={t['hits']}")
                lines.append(f"   reply: _{reply}_")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n\n=== Classifica finale ===")
    for m, r in ranking:
        print(f"  {m:30}  agg={r['aggregate']:.1f}  A={r['a_retrieval']:.0f} B={r['b_facts']:.0f} C={r['c_tags']:.0f} D={r['d_multiturn']:.0f}  {r['avg_time']:.1f}s")
    print(f"\nReport: {out}")
    db.close()


if __name__ == "__main__":
    main()
