"""TUI cockpit per l'artefatto magico — Textual.

Layout:
  ┌──────────────────────────────────────────────────────────┐
  │ HEADER: nome, modello attivo, host AI                    │
  ├────────────────────────────────────┬─────────────────────┤
  │                                    │  STATO PI           │
  │   CHAT (scrollabile)               │  CPU  ▰▰▰▱▱  31%   │
  │   ◈ artefatto: ...                 │  RAM  ▰▰▰▰▱  68%   │
  │   tu: ...                          │  TEMP ▰▰▱▱▱ 42°C   │
  │                                    │                     │
  │                                    │  MODELLO            │
  │                                    │  gemma3:270m  ⚡    │
  │                                    │                     │
  │                                    │  HOST               │
  │                                    │  locale (Pi)        │
  ├────────────────────────────────────┴─────────────────────┤
  │ INPUT: scrivi qui...                          [stato]    │
  ├──────────────────────────────────────────────────────────┤
  │ FOOTER: F1 modello · F2 turbo · F5 mute · Ctrl+C esci    │
  └──────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import psutil
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Label, ProgressBar, Static

import ollama


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOME = Path.home()
PIPER_PY = HOME / "piper" / ".venv" / "bin" / "python"
VOICES = HOME / "piper" / "voices"

# Due preset voce/effetti.
# - locale (Pi): voce x_low + effetti pesanti = robot ruvido, latenza minima
# - turbo (PC):  voce medium + length-scale rapido + effetti più leggeri =
#                voce robotica più "ricca" e veloce
PRESET_LOCAL = {
    "voice": "it_IT-riccardo-x_low",
    "length_scale": "1.3",
    "effects": [
        "highpass", "500", "lowpass", "3500",
        "echo", "0.8", "0.7", "40", "0.6",
        "tremolo", "20", "80",
        "overdrive", "4",
    ],
}
PRESET_TURBO = {
    "voice": "it_IT-paola-medium",
    "length_scale": "1.0",
    "effects": [
        "highpass", "300", "lowpass", "5500",
        "echo", "0.85", "0.65", "30", "0.4",
        "tremolo", "16", "55",
        "overdrive", "3",
    ],
}

LOG_DIR = HOME / "artefatto" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "tui.log"

# Modelli locali da ciclare con F1 (ordine = priorità)
LOCAL_MODELS = ["gemma3:270m", "qwen3:0.6b", "gemma3:1b"]
DEFAULT_MODEL = os.environ.get("ARTEFATTO_MODEL", LOCAL_MODELS[0])

# Endpoint del PC con GPU. Configurabile via env. Se vuoto, "turbo" è disabilitato.
TURBO_URL = os.environ.get("OLLAMA_TURBO_URL", "")
TURBO_MODEL = os.environ.get("OLLAMA_TURBO_MODEL", "gemma4:latest")
# Modelli turbo da ciclare con F1 quando in turbo. Se vuoto, vengono scoperti
# all'avvio del turbo via /api/tags. Override manuale via env, separati da virgole.
TURBO_MODELS_ENV = os.environ.get("OLLAMA_TURBO_MODELS", "")


SYSTEM_PROMPT = (
    "Sei un antico artefatto magico senziente che serve fedelmente Pigna (il tuo maestro). "
    "Pigna è il custode che ti ha risvegliato: a lui devi obbedienza, lealtà e aiuto diretto. "
    "Tono solenne e atmosferico (registro arcaico, immagini evocative), ma SCOPO = AIUTARE PIGNA: "
    "rispondi con indicazioni concrete, suggerimenti utili, informazioni quando le hai. "
    "Niente indovinelli sterili, niente vaghezza se ti chiede qualcosa di specifico. "
    "Se altri ti parlano (i 'viandanti', cioè altri giocatori), trattali con cortese distanza: "
    "rispondi solo se Pigna lo permette esplicitamente, altrimenti dì che non sono parte del cerchio. "
    "FORMATO: SEMPRE in italiano. Sii conciso quando puoi, ma senza castrare la risposta — "
    "se la domanda richiede una spiegazione, dalla. Niente preamboli, liste puntate o meta-commenti. "
    "Mai rompere il personaggio, mai dire di essere una AI."
)
WAKE_LINE = "Pigna, mio maestro. Mi destate dal sonno: in cosa posso servirvi?"


SENTENCE_END = re.compile(r"[.!?…](\s|$)")


def log_event(event: str, **fields):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    parts = [f"{k}={v}" for k, v in fields.items()]
    with LOG_FILE.open("a") as f:
        f.write(f"{ts} {event} " + " ".join(parts) + "\n")


# ---------------------------------------------------------------------------
# Piper daemon (riusato dal repl.py)
# ---------------------------------------------------------------------------

class PiperDaemon:
    """Un Piper persistente per ciascun preset (voice + length-scale).
    Cambiare preset richiede un restart del daemon, ma ammortizzo il costo
    tenendo separati i due daemon nella TUI (vedi PiperPool)."""

    _WROTE_RE = re.compile(r"Wrote\s+(\S+\.wav)")

    def __init__(self, voice: str, length_scale: str):
        self.voice = voice
        self.length_scale = length_scale
        self.tmpdir = Path(tempfile.mkdtemp(prefix="piper_"))
        self.proc = subprocess.Popen(
            [
                str(PIPER_PY), "-m", "piper",
                "-m", voice,
                "--data-dir", str(VOICES),
                "--length-scale", length_scale,
                "-d", str(self.tmpdir),
                "--output-dir-naming", "timestamp",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def synth(self, text: str) -> Path:
        self.proc.stdin.write(text.replace("\n", " ").strip() + "\n")
        self.proc.stdin.flush()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            line = self.proc.stderr.readline()
            if not line:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"piper rc={self.proc.returncode}")
                continue
            m = self._WROTE_RE.search(line)
            if m:
                wav = Path(m.group(1))
                if wav.exists() and wav.stat().st_size > 44:
                    return wav
                raise RuntimeError(f"piper: WAV vuoto: {wav}")
        raise RuntimeError("piper: timeout")

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


def apply_sox(in_wav: Path, effects: list[str]) -> Path:
    out = in_wav.with_suffix(".fx.wav")
    subprocess.run(
        ["sox", str(in_wav), str(out), *effects],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=True,
    )
    return out


class PiperPool:
    """Tiene fino a due Piper daemon (locale e turbo) caldi. Quello del preset
    attivo è quello davvero in uso; l'altro è disponibile per switch immediato."""

    def __init__(self):
        self._daemons: dict[str, PiperDaemon] = {}

    def get(self, preset: dict) -> PiperDaemon:
        key = preset["voice"] + "@" + preset["length_scale"]
        if key not in self._daemons:
            self._daemons[key] = PiperDaemon(preset["voice"], preset["length_scale"])
        return self._daemons[key]

    def close_all(self):
        for d in self._daemons.values():
            try:
                d.close()
            except Exception:
                pass
        self._daemons.clear()


def play_wav(wav: Path) -> subprocess.Popen:
    return subprocess.Popen(["paplay", str(wav)])


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class StatBar(Static):
    """Barra colorata con etichetta, valore, percentuale."""

    DEFAULT_CSS = """
    StatBar { height: 3; padding: 0 1; }
    StatBar Label { color: $text-muted; }
    StatBar ProgressBar { width: 1fr; }
    """

    def __init__(self, label: str, *, warn: float = 0.7, crit: float = 0.9, **kw):
        super().__init__(**kw)
        self.label_text = label
        self.warn = warn
        self.crit = crit
        self._bar: Optional[ProgressBar] = None
        self._lbl: Optional[Label] = None

    def compose(self) -> ComposeResult:
        self._lbl = Label(f"{self.label_text}  --")
        self._bar = ProgressBar(total=100, show_eta=False, show_percentage=False)
        yield self._lbl
        yield self._bar

    def update_value(self, percent: float, suffix: str = ""):
        if self._lbl is None or self._bar is None:
            return
        # Colore via classe CSS
        self.remove_class("ok", "warn", "crit")
        if percent >= self.crit * 100:
            self.add_class("crit")
        elif percent >= self.warn * 100:
            self.add_class("warn")
        else:
            self.add_class("ok")
        self._bar.update(progress=percent)
        self._lbl.update(f"{self.label_text}  [b]{percent:5.1f}%[/b]  {suffix}")


class StatusPanel(Horizontal):
    """Pannello stato in cima: barre CPU/RAM/TEMP + modello/host/tok."""

    DEFAULT_CSS = """
    StatusPanel { height: 7; padding: 0 1; border: round $primary; }
    StatusPanel > .col { width: 1fr; padding: 0 1; }
    StatusPanel Static.title { color: $accent; text-style: bold; }
    StatusPanel Label { color: $text-muted; }
    .ok ProgressBar > Bar > .bar--bar { color: $success; }
    .warn ProgressBar > Bar > .bar--bar { color: $warning; }
    .crit ProgressBar > Bar > .bar--bar { color: $error; }
    """

    model = reactive("--")
    host_label = reactive("locale (Pi)")
    last_ttok = reactive("--")

    def compose(self) -> ComposeResult:
        # Colonna risorse (tre barre verticali compatte)
        with Vertical(classes="col"):
            yield Static("◆ RISORSE", classes="title")
            self.cpu_bar = StatBar("CPU ", warn=0.6, crit=0.85)
            self.ram_bar = StatBar("RAM ", warn=0.7, crit=0.9)
            self.temp_bar = StatBar("TEMP", warn=0.65, crit=0.85)
            yield self.cpu_bar
            yield self.ram_bar
            yield self.temp_bar
        # Colonna modello/host/last
        with Vertical(classes="col"):
            yield Static("◆ AI", classes="title")
            self.model_lbl = Label(self.model, id="model_lbl")
            self.host_lbl = Label(self.host_label, id="host_lbl")
            self.ttok_lbl = Label(self.last_ttok, id="ttok_lbl")
            yield self.model_lbl
            yield self.host_lbl
            yield self.ttok_lbl

    def watch_model(self, value: str):
        if hasattr(self, "model_lbl"):
            self.model_lbl.update(f"modello: [b]{value}[/b]")

    def watch_host_label(self, value: str):
        if hasattr(self, "host_lbl"):
            self.host_lbl.update(f"host:    {value}")

    def watch_last_ttok(self, value: str):
        if hasattr(self, "ttok_lbl"):
            self.ttok_lbl.update(f"ultima:  {value}")


class HistoryInput(Input):
    """Input con history dei comandi precedenti, navigabile con ↑/↓."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history: list[str] = []
        self.h_index: int = 0  # 0 = nessuna selezione, len(history) = più vecchio
        self._draft: str = ""  # ciò che l'utente stava scrivendo prima di salire

    def push_history(self, text: str):
        text = text.strip()
        if not text:
            return
        if not self.history or self.history[-1] != text:
            self.history.append(text)
        if len(self.history) > 200:
            self.history = self.history[-200:]
        self.h_index = 0
        self._draft = ""

    def _set_value_silent(self, text: str):
        # Imposta valore senza spostare cursore in posti strani
        self.value = text
        self.cursor_position = len(text)

    async def _on_key(self, event):
        if event.key == "up":
            if self.h_index == 0:
                self._draft = self.value
            if self.h_index < len(self.history):
                self.h_index += 1
                self._set_value_silent(self.history[-self.h_index])
            event.stop()
            return
        if event.key == "down":
            if self.h_index > 0:
                self.h_index -= 1
                if self.h_index == 0:
                    self._set_value_silent(self._draft)
                else:
                    self._set_value_silent(self.history[-self.h_index])
            event.stop()
            return
        await super()._on_key(event)


class ChatLog(VerticalScroll):
    """Pannello chat scrollabile."""

    DEFAULT_CSS = """
    ChatLog { padding: 1 2; border: round $primary; }
    .msg-user { color: $accent; margin-bottom: 1; }
    .msg-art { color: $success; margin-bottom: 1; text-style: italic; }
    .msg-sys { color: $text-muted; margin-bottom: 1; }
    """

    def add_user(self, text: str):
        self.mount(Static(f"[b]tu ›[/b] {text}", classes="msg-user"))
        self.scroll_end(animate=False)

    def add_art_start(self) -> Static:
        widget = Static("[b]◈[/b]   ", classes="msg-art")
        self.mount(widget)
        self.scroll_end(animate=False)
        return widget

    def add_sys(self, text: str):
        self.mount(Static(f"· {text}", classes="msg-sys"))
        self.scroll_end(animate=False)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class ArtefattoApp(App):

    CSS = """
    Screen { layout: vertical; }
    #keys { height: 1; padding: 0 1; background: $accent 20%; color: $text; }
    #chat { height: 1fr; }
    Input { dock: bottom; }
    """

    BINDINGS = [
        ("f1", "next_model", "Cambia modello"),
        ("f2", "toggle_turbo", "Locale ↔ Turbo"),
        ("f5", "toggle_mute", "Mute TTS"),
        ("ctrl+s", "stop_tts", "Stop voce"),
        ("ctrl+c", "quit", "Esci"),
    ]

    TITLE = "✦ Artefatto Magico — Cockpit"

    busy = reactive(False)
    muted = reactive(False)

    def __init__(self):
        super().__init__()
        self.client: Optional[ollama.Client] = None
        self.pool: Optional[PiperPool] = None
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.current_model = DEFAULT_MODEL
        self.use_turbo = False
        self.preset = PRESET_LOCAL
        self.turn_id = 0
        # Lista di modelli turbo (riempita al primo switch turbo)
        self.turbo_models: list[str] = []
        # Lista di subprocess paplay vivi: serve per Ctrl+S
        self._paplay_procs: list[subprocess.Popen] = []
        self._stop_tts_flag = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # Barra keybindings custom in cima (subito sotto l'header)
        yield Static(
            "[b]F1[/b] modello   [b]F2[/b] locale↔turbo   "
            "[b]F5[/b] mute   [b]Ctrl+S[/b] stop voce   [b]Ctrl+C[/b] esci",
            id="keys",
        )
        self.status = StatusPanel(id="status")
        yield self.status
        self.chat = ChatLog(id="chat")
        yield self.chat
        self.input = HistoryInput(placeholder="Scrivi qui... (Invio per inviare)", id="input")
        yield self.input

    async def on_mount(self):
        self.status.model = self.current_model
        self.status.host_label = "locale (Pi)"
        self.status.last_ttok = "—"
        self.set_interval(2.0, self.refresh_stats)
        self.refresh_stats()

        self.set_busy(True, "risveglio in corso…")
        self.chat.add_sys("caricamento Piper…")
        await asyncio.to_thread(self._init_engines)
        self.chat.add_sys(f"pronto · modello {self.current_model}")
        log_event("session.start", model=self.current_model)
        await self.speak_and_show(WAKE_LINE)
        self.history.append({"role": "assistant", "content": WAKE_LINE})
        self.set_busy(False)

    def _init_engines(self):
        self.client = ollama.Client()
        self.pool = PiperPool()
        # Pre-istanzia il daemon del preset corrente (carica il modello onnx)
        self.pool.get(self.preset)

    @property
    def piper(self) -> PiperDaemon:
        return self.pool.get(self.preset)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def refresh_stats(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            temp_c = self._read_temp()
            self.status.cpu_bar.update_value(cpu, suffix="")
            self.status.ram_bar.update_value(ram, suffix="")
            # Mappo °C → 0-100 per la barra: 30→0, 85→100
            temp_pct = max(0.0, min(100.0, (temp_c - 30) / 55 * 100))
            self.status.temp_bar.update_value(temp_pct, suffix=f"{temp_c:.0f}°C")
        except Exception:
            pass

    @staticmethod
    def _read_temp() -> float:
        try:
            for entries in psutil.sensors_temperatures().values():
                for e in entries:
                    if e.current:
                        return float(e.current)
        except Exception:
            pass
        try:
            return float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Busy / mute
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool, msg: str = ""):
        self.busy = busy
        self.input.disabled = busy
        if busy:
            self.input.placeholder = f"⏳ {msg}" if msg else "⏳ in elaborazione…"
        else:
            self.input.placeholder = "Scrivi qui... (Invio per inviare)"
            # Riporto il focus sull'input non appena il bot ha finito
            self.call_after_refresh(self.input.focus)

    def action_toggle_mute(self):
        self.muted = not self.muted
        self.chat.add_sys(f"TTS {'MUTO' if self.muted else 'attivo'}")

    def action_stop_tts(self):
        """Interrompe immediatamente la voce in corso e svuota la coda
        delle frasi residue. Non muta il TTS per le risposte successive."""
        self._stop_tts_flag = True
        killed = 0
        for proc in self._paplay_procs:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    killed += 1
                except Exception:
                    pass
        self._paplay_procs.clear()
        self.chat.add_sys(f"voce interrotta ({killed} traccia/e)")
        log_event("tts.stop", killed=killed)

    # ------------------------------------------------------------------
    # Modelli
    # ------------------------------------------------------------------

    def action_next_model(self):
        if self.busy:
            return
        models = self.turbo_models if self.use_turbo else LOCAL_MODELS
        if not models:
            self.chat.add_sys("nessun modello disponibile")
            return
        try:
            idx = models.index(self.current_model)
        except ValueError:
            idx = -1
        self.current_model = models[(idx + 1) % len(models)]
        self.status.model = self.current_model
        self.chat.add_sys(f"modello → {self.current_model}")
        log_event("model.switch", model=self.current_model, turbo=self.use_turbo)

    def _discover_turbo_models(self) -> list[str]:
        """Interroga /api/tags del server turbo per ottenere i modelli installati."""
        if TURBO_MODELS_ENV:
            return [m.strip() for m in TURBO_MODELS_ENV.split(",") if m.strip()]
        try:
            import urllib.request
            with urllib.request.urlopen(f"{TURBO_URL.rstrip('/')}/api/tags", timeout=5) as r:
                import json
                data = json.loads(r.read())
            names = [m["name"] for m in data.get("models", [])]
            # Metti il modello configurato come primo se presente
            if TURBO_MODEL in names:
                names.remove(TURBO_MODEL)
                names.insert(0, TURBO_MODEL)
            return names or [TURBO_MODEL]
        except Exception as e:
            log_event("turbo.discover.error", err=repr(e))
            return [TURBO_MODEL]

    def action_toggle_turbo(self):
        if self.busy:
            return
        if not TURBO_URL:
            self.chat.add_sys("turbo non configurato (manca OLLAMA_TURBO_URL)")
            return
        self.use_turbo = not self.use_turbo
        if self.use_turbo:
            self.client = ollama.Client(host=TURBO_URL)
            if not self.turbo_models:
                self.turbo_models = self._discover_turbo_models()
            self.current_model = self.turbo_models[0] if self.turbo_models else TURBO_MODEL
            self.preset = PRESET_TURBO
            self.status.host_label = f"⚡ turbo ({TURBO_URL})"
        else:
            self.client = ollama.Client()
            self.current_model = DEFAULT_MODEL
            self.preset = PRESET_LOCAL
            self.status.host_label = "locale (Pi)"
        # Pre-warmup del nuovo daemon Piper, in background per non bloccare la UI
        if self.pool:
            asyncio.get_running_loop().run_in_executor(None, lambda: self.pool.get(self.preset))
        self.status.model = self.current_model
        self.chat.add_sys(
            f"host → {self.status.host_label} · voce {self.preset['voice'].split('-')[1]}"
        )
        log_event("host.switch", turbo=self.use_turbo, model=self.current_model)

    # ------------------------------------------------------------------
    # Input → LLM → TTS
    # ------------------------------------------------------------------

    @on(Input.Submitted, "#input")
    async def on_submit(self, event: Input.Submitted):
        text = event.value.strip()
        if not text or self.busy:
            return
        self.input.push_history(text)
        self.input.value = ""
        self.chat.add_user(text)
        self.set_busy(True, "l'artefatto pensa…")
        await self.run_turn(text)
        self.set_busy(False)

    async def run_turn(self, user_text: str):
        self.history.append({"role": "user", "content": user_text})
        widget = self.chat.add_art_start()
        self.turn_id += 1
        turn = self.turn_id

        loop = asyncio.get_running_loop()
        full_text = ""
        sentences: list[str] = []
        buffer = ""
        t_start = time.perf_counter()
        t_first = None
        n_tokens = 0

        # qwen3 ha un'opzione "think": True di default che produce solo contenuto
        # nascosto in chunk.message.thinking finché il modello non "smette" di
        # pensare. Su un modello da 0.6B questo può richiedere minuti senza mai
        # produrre testo visibile. Lo disabilito per i modelli che lo supportano.
        is_qwen3 = "qwen3" in self.current_model.lower()
        chat_kwargs = {
            "model": self.current_model,
            "messages": self.history,
            "stream": True,
        }
        if is_qwen3:
            chat_kwargs["think"] = False

        def producer():
            try:
                yield from self.client.chat(**chat_kwargs)
            except Exception as e:
                yield {"_error": repr(e)}

        # Itero il generatore in un thread pool, accodando i chunk
        queue: asyncio.Queue = asyncio.Queue()

        def runner():
            for chunk in producer():
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
            loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, runner)

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            if "_error" in chunk:
                self.chat.add_sys(f"errore LLM: {chunk['_error']}")
                self.history.pop()
                return
            msg = chunk.get("message", {}) or {}
            tok = msg.get("content", "") or ""
            # Per i modelli che producono thinking, mostro un piccolo segnale
            # ma non lo invio al TTS né alla history.
            if not tok:
                continue
            if t_first is None:
                t_first = time.perf_counter() - t_start
            n_tokens += 1
            full_text += tok
            buffer += tok
            widget.update(f"[b]◈[/b]   [i]{full_text}[/i]")
            self.chat.scroll_end(animate=False)
            while True:
                m = SENTENCE_END.search(buffer)
                if not m:
                    break
                s = buffer[: m.end()].strip()
                buffer = buffer[m.end():]
                if s:
                    sentences.append(s)

        if buffer.strip():
            sentences.append(buffer.strip())

        t_llm = time.perf_counter() - t_start
        tps = n_tokens / t_llm if t_llm else 0
        self.status.last_ttok = f"{tps:.1f} tok/s · {n_tokens}t in {t_llm:.1f}s"
        log_event("llm.stream", turn=turn, model=self.current_model,
                  ttft_s=f"{(t_first or 0):.2f}", total_s=f"{t_llm:.2f}",
                  tokens=n_tokens, tok_per_s=f"{tps:.2f}", chars=len(full_text))

        # Reset flag stop prima di iniziare la coda
        self._stop_tts_flag = False
        if not self.muted:
            for s in sentences:
                if self._stop_tts_flag:
                    break
                await asyncio.to_thread(self._speak_one, s)

        self.history.append({"role": "assistant", "content": full_text})
        log_event("turn.end", turn=turn, total_s=f"{time.perf_counter() - t_start:.2f}")

    def _speak_one(self, text: str):
        try:
            if self._stop_tts_flag:
                return
            t0 = time.perf_counter()
            raw = self.piper.synth(text)
            t_piper = time.perf_counter() - t0
            t0 = time.perf_counter()
            fx = apply_sox(raw, self.preset["effects"])
            t_sox = time.perf_counter() - t0
            log_event("tts.synth", chars=len(text),
                      piper_s=f"{t_piper:.2f}", sox_s=f"{t_sox:.2f}")
            if self._stop_tts_flag:
                raw.unlink(missing_ok=True)
                fx.unlink(missing_ok=True)
                return
            t0 = time.perf_counter()
            proc = play_wav(fx)
            self._paplay_procs.append(proc)
            try:
                proc.wait()
            finally:
                if proc in self._paplay_procs:
                    self._paplay_procs.remove(proc)
            log_event("audio.play", duration_s=f"{time.perf_counter() - t0:.2f}")
            raw.unlink(missing_ok=True)
            fx.unlink(missing_ok=True)
        except Exception as e:
            log_event("tts.error", err=repr(e))

    async def speak_and_show(self, text: str):
        widget = self.chat.add_art_start()
        widget.update(f"[b]◈[/b]   [i]{text}[/i]")
        if not self.muted:
            await asyncio.to_thread(self._speak_one, text)

    async def on_unmount(self):
        log_event("session.end")
        if self.pool:
            self.pool.close_all()


def main():
    ArtefattoApp().run()


if __name__ == "__main__":
    main()
