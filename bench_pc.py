"""Benchmark dei modelli Ollama installati sul PC remoto.

Per ogni modello fa due chiamate (cold + warm), misura ttft, tps, output.
Genera anche bench_pc_results.md con tabella ordinata e output di esempio.
"""
from __future__ import annotations

import io
import sys
import time
import urllib.request
import json
from pathlib import Path

# Forzo UTF-8 sullo stdout per non rompere su simboli tipo → ✓ ⚡
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HOST = "http://192.168.1.100:11434"

SYSTEM = (
    "Sei un antico artefatto magico senziente che assiste i giocatori. "
    "Tono solenne, atmosferico, registro arcaico. SCOPO: aiutare con risposte concrete. "
    "FORMATO: italiano, 1-3 frasi (max 40 parole). Niente liste, niente preamboli."
)
PROMPT = "Maestro, ho trovato una porta antica con tre rune sopra. Cosa significa?"

GENERALIST = [
    "gemma4:latest",
    "qwen3:14b",
    "qwen3:8b",
    "gemma3:12b",
    "mistral-nemo:12b",
    "llama3.1:8b",
]


def list_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{HOST}/api/tags", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def chat_once(model: str, prompt: str, system: str = SYSTEM) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
    }
    if "qwen3" in model.lower():
        body["think"] = False

    req = urllib.request.Request(
        f"{HOST}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    t0 = time.perf_counter()
    t_first = None
    n_tokens = 0
    full = ""
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            tok = obj.get("message", {}).get("content", "") or ""
            if tok:
                if t_first is None:
                    t_first = time.perf_counter() - t0
                n_tokens += 1
                full += tok
            if obj.get("done"):
                break
    total = time.perf_counter() - t0
    return {
        "model": model,
        "ttft_s": t_first or 0.0,
        "total_s": total,
        "tokens": n_tokens,
        "tps": n_tokens / total if total > 0 else 0.0,
        "output": full.strip(),
    }


def run_round(models: list[str], label: str) -> list[dict]:
    print(f"\n--- {label} ---")
    results = []
    for m in models:
        try:
            r = chat_once(m, PROMPT)
            print(f"  {r['model']:22s}  ttft={r['ttft_s']:5.2f}s  "
                  f"tot={r['total_s']:6.2f}s  tps={r['tps']:6.2f}  "
                  f"chars={len(r['output']):4d}")
            preview = r['output'][:140].replace('\n', ' ')
            print(f"    > {preview}{'...' if len(r['output'])>140 else ''}")
            results.append(r)
        except Exception as e:
            print(f"  {m:22s}  ERROR: {e}")
    return results


def main():
    print("=" * 78)
    print("BENCHMARK ARTEFATTO — modelli Ollama PC (RX 6800)")
    print(f"Host: {HOST}")
    print(f"Prompt: {PROMPT!r}")
    print("=" * 78)

    available = list_models()
    print(f"\nModelli disponibili sul server: {len(available)}")
    for m in available:
        print(f"  - {m}")

    targets = [m for m in GENERALIST if m in available]
    missing = [m for m in GENERALIST if m not in available]
    if missing:
        print(f"\n[skip] non installati: {', '.join(missing)}")

    run_round(targets, "RUN 1 (cold load: include caricamento VRAM)")
    warm = run_round(targets, "RUN 2 (warm: velocita' stabile)")

    print("\n" + "=" * 78)
    print("CLASSIFICA WARM (per tps)")
    print("=" * 78)
    warm_sorted = sorted(warm, key=lambda x: -x["tps"])
    for r in warm_sorted:
        print(f"  {r['model']:22s}  tps={r['tps']:6.2f}  "
              f"tot={r['total_s']:6.2f}s  chars={len(r['output']):4d}")

    # Salva un report markdown
    report = Path("bench_pc_results.md")
    with report.open("w", encoding="utf-8") as f:
        f.write("# Benchmark modelli Ollama PC\n\n")
        f.write(f"Hardware: RX 6800 16GB · Host: `{HOST}`\n\n")
        f.write(f"Prompt: `{PROMPT}`\n\n")
        f.write("## Risultati (run 2 warm)\n\n")
        f.write("| Modello | tps | total s | ttft s | chars |\n")
        f.write("|---|---:|---:|---:|---:|\n")
        for r in warm_sorted:
            f.write(f"| `{r['model']}` | {r['tps']:.2f} | "
                    f"{r['total_s']:.2f} | {r['ttft_s']:.2f} | {len(r['output'])} |\n")
        f.write("\n## Output di esempio\n\n")
        for r in warm_sorted:
            f.write(f"### {r['model']}\n\n> {r['output']}\n\n")
    print(f"\nReport scritto in {report}")


if __name__ == "__main__":
    main()
