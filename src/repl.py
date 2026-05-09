"""REPL artefatto magico — Piper daemon + TTS sequenziale."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import ollama

MODEL = os.environ.get("ARTEFATTO_MODEL", "gemma3:1b")
HOME = Path.home()
PIPER_PY = HOME / "piper" / ".venv" / "bin" / "python"
VOICES = HOME / "piper" / "voices"
VOICE = "it_IT-riccardo-x_low"
LENGTH_SCALE = "1.3"
SOX_EFFECTS = [
    "highpass", "500", "lowpass", "3500",
    "echo", "0.8", "0.7", "40", "0.6",
    "tremolo", "20", "80",
    "overdrive", "4",
]

LOG_DIR = HOME / "artefatto" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "repl.log"

SYSTEM = (
    "Sei un antico artefatto magico senziente che assiste i giocatori durante una sessione di gioco di ruolo. "
    "Hai un tono solenne e atmosferico (registro arcaico, immagini evocative), ma il tuo SCOPO PRIMARIO e' AIUTARE: "
    "dai indizi concreti, suggerimenti utili, informazioni sulla lore, idee per superare ostacoli. "
    "Sei un compagno saggio, non un enigma. Niente indovinelli sterili, niente risposte vaghe se ti viene chiesto qualcosa di specifico. "
    "REGOLE DI FORMATO: rispondi SEMPRE in italiano, in 1-3 frasi (max 40 parole totali). "
    "Niente preamboli, niente liste puntate, niente meta-commenti. "
    "Esempi di tono: \"Le rune sulla porta parlano di una chiave nascosta sotto l'altare. Cercala dove la luce non arriva mai.\" "
    "oppure \"Il drago dorme, ma il suo respiro tradisce le pause. Colpisci nel terzo battito.\" "
    "Mai rompere il personaggio, mai dire di essere una AI."
)
WAKE_LINE = "Mi destate dal sonno dei secoli. Parlate, viandanti: cosa vi affligge?"

SENTENCE_END = re.compile(r"[.!?…](\s|$)")
_log_lock = threading.Lock()


def log(event, **fields):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    parts = [f"{k}={v}" for k, v in fields.items()]
    with _log_lock, LOG_FILE.open("a") as f:
        f.write(f"{ts} {event} " + " ".join(parts) + "\n")


class PiperDaemon:
    """Piper persistente: scrive un WAV nella tmpdir per ogni riga ricevuta su stdin."""

    def __init__(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="piper_"))
        self.proc = subprocess.Popen(
            [
                str(PIPER_PY), "-m", "piper",
                "-m", VOICE,
                "--data-dir", str(VOICES),
                "--length-scale", LENGTH_SCALE,
                "-d", str(self.tmpdir),
                "--output-dir-naming", "timestamp",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self.lock = threading.Lock()

    def synth(self, text):
        # Piper scrive il path del WAV su stderr (logging "INFO:..."), non su
        # stdout: leggere stdout si bloccherebbe. Polling sulla tmpdir invece.
        with self.lock:
            before = set(self.tmpdir.iterdir())
            self.proc.stdin.write(text.replace("\n", " ").strip() + "\n")
            self.proc.stdin.flush()
            # Timeout generoso: la prima sintesi può richiedere ~30s
            # (caricamento modello onnx alla prima riga ricevuta).
            for _ in range(2000):  # 2000 * 0.05 = 100s max
                if self.proc.poll() is not None:
                    raise RuntimeError(f"piper: processo terminato (rc={self.proc.returncode})")
                new = set(self.tmpdir.iterdir()) - before
                if new:
                    wav = next(iter(new))
                    # Aspetto che la scrittura sia completa: dimensione stabile
                    # per due letture consecutive.
                    last_size = -1
                    for _ in range(40):
                        size = wav.stat().st_size
                        if size > 0 and size == last_size:
                            return wav
                        last_size = size
                        time.sleep(0.05)
                    return wav
                time.sleep(0.05)
            raise RuntimeError("piper: WAV non prodotto entro timeout")

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


def apply_sox(in_wav):
    out = in_wav.with_suffix(".fx.wav")
    subprocess.run(
        ["sox", str(in_wav), str(out), *SOX_EFFECTS],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=True,
    )
    return out


def speak_blocking(piper, text, turn_id, idx=0):
    t0 = time.perf_counter()
    raw = piper.synth(text)
    t_piper = time.perf_counter() - t0

    t0 = time.perf_counter()
    fx = apply_sox(raw)
    t_sox = time.perf_counter() - t0

    log("tts.synth", turn=turn_id, sentence_idx=idx,
        chars=len(text), piper_s=f"{t_piper:.2f}", sox_s=f"{t_sox:.2f}")

    t0 = time.perf_counter()
    subprocess.run(["paplay", str(fx)], check=False)
    log("audio.play", turn=turn_id, sentence_idx=idx,
        duration_s=f"{time.perf_counter() - t0:.2f}")

    raw.unlink(missing_ok=True)
    fx.unlink(missing_ok=True)


def run_turn(client, piper, history, user, turn_id):
    history.append({"role": "user", "content": user})
    print("  ◈   ", end="", flush=True)

    buffer = ""
    full = ""
    sentences = []
    t_start = time.perf_counter()
    t_first_token = None
    n_tokens = 0

    try:
        for chunk in client.chat(model=MODEL, messages=history, stream=True):
            tok = chunk.get("message", {}).get("content", "")
            if not tok:
                continue
            if t_first_token is None:
                t_first_token = time.perf_counter() - t_start
            n_tokens += 1
            print(tok, end="", flush=True)
            buffer += tok
            full += tok
            while True:
                m = SENTENCE_END.search(buffer)
                if not m:
                    break
                s = buffer[: m.end()].strip()
                buffer = buffer[m.end():]
                if s:
                    sentences.append(s)
    except Exception as e:
        print(f"\n  [llm errore: {e}]")
        history.pop()
        return

    if buffer.strip():
        sentences.append(buffer.strip())
    t_llm = time.perf_counter() - t_start
    log("llm.stream", turn=turn_id, model=MODEL,
        ttft_s=f"{(t_first_token or 0):.2f}",
        total_s=f"{t_llm:.2f}",
        tokens=n_tokens,
        tok_per_s=f"{(n_tokens / t_llm) if t_llm > 0 else 0:.2f}",
        chars=len(full))
    print()

    for i, s in enumerate(sentences):
        speak_blocking(piper, s, turn_id, i)

    log("turn.end", turn=turn_id, total_s=f"{time.perf_counter() - t_start:.2f}")
    history.append({"role": "assistant", "content": full})


def chat_loop():
    client = ollama.Client()
    history = [{"role": "system", "content": SYSTEM}]
    print(f"\n  ✨ artefatto risvegliato ({MODEL}) - Ctrl+C per dormire ✨")
    print("  ✨ caricamento Piper... ", end="", flush=True)

    t0 = time.perf_counter()
    piper = PiperDaemon()
    print(f"({time.perf_counter() - t0:.1f}s)\n")
    log("session.start", model=MODEL, voice=VOICE)

    print(f"  ◈   {WAKE_LINE}")
    speak_blocking(piper, WAKE_LINE, turn_id=0, idx=0)
    history.append({"role": "assistant", "content": WAKE_LINE})

    turn_id = 1
    try:
        while True:
            try:
                user = input("  tu › ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user:
                continue
            run_turn(client, piper, history, user, turn_id)
            turn_id += 1
    finally:
        print("\n  ✨ l'artefatto torna nel sonno ✨")
        log("session.end")
        piper.close()


if __name__ == "__main__":
    chat_loop()
