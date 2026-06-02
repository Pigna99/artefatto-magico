"""TUI cockpit per l'artefatto magico — Textual.

Layout:
  ┌──────────────────────────────────────────────────────────┐
  │ HEADER + keybindings                                     │
  ├────────────────────────────────────┬─────────────────────┤
  │ STATUS PANEL (CPU/RAM/TEMP + AI info)                    │
  ├──────────────────────────────────────────────────────────┤
  │ CHAT (scrollabile)                                       │
  ├──────────────────────────────────────────────────────────┤
  │ INPUT                                                    │
  └──────────────────────────────────────────────────────────┘

Questo file è l'entry point. La logica è suddivisa in:
  - config.py       costanti, env, system prompt
  - widgets.py      StatBar, StatusPanel, HistoryInput, ChatLog
  - tts/            Piper daemon, edge-tts client, sanitize
  - llm.py          streaming Ollama + RAG injection
  - commands.py     /lore /codex /roll
  - audio.py        paplay queue + stop
  - db.py           SQLite + FTS5
  - gpio_fx.py      LED + buzzer + tag parser
"""
from __future__ import annotations

import asyncio
import random
import subprocess
import time
from pathlib import Path
from typing import Optional

import psutil
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Header, Input, Static

import ollama

from config import (
    DB_PATH, DEFAULT_MODEL, LOCAL_MODELS, PRESET_LOCAL, PRESET_TURBO,
    START_TURBO, SYSTEM_PROMPT, TURBO_BACKEND, TURBO_MODEL, TURBO_MODELS_ENV,
    TURBO_URL, WAKE_LINE, EDGE_TTS_ENABLED, EDGE_TTS_VOICE, EDGE_TTS_RATE,
    log_event,
)
from widgets import ChatLog, HistoryInput, StatusPanel
from tts import (
    PiperDaemon, PiperPool, apply_sox, sanitize_for_tts, split_sentences,
    AllTalkClient,
)
from llm import OpenAIClient, StickyContext, build_messages_with_rag, chat_kwargs, stream_chat
from commands import handle_slash
from audio import AudioPlayer

try:
    from db import Database
except Exception:  # noqa: BLE001
    Database = None  # type: ignore

try:
    from gpio_fx import GpioFx, consume_tags
except Exception:  # noqa: BLE001
    GpioFx = None  # type: ignore
    def consume_tags(text, fx):
        return text


INPUT_MODES = [
    # (key, title, border_color, placeholder)
    ("libera", "LIBERA",  "$success", "Scrivi qui... (Invio per inviare)"),
    ("codex",  "CODEX",   "$warning", "Codex: <titolo> <testo>  (aggiunge una voce di codex)"),
    ("roll",   "ROLL",    "$accent",  "Roll: d20 oppure 2d6  (tira dadi)"),
    ("lore",   "LORE",    "magenta",  "Lore: <kind> <nome> <descrizione>  (kind: npc/place/item/event/note)"),
]


class ArtefattoApp(App):
    CSS = """
    Screen { layout: vertical; }
    #keys { height: 1; padding: 0 1; background: $accent 20%; color: $text; }
    #chat { height: 1fr; }
    Input { dock: bottom; border: tall $success; }
    Input.mode-libera { border: tall $success; }
    Input.mode-codex  { border: tall $warning; }
    Input.mode-roll   { border: tall $accent; }
    Input.mode-lore   { border: tall magenta; }
    """

    BINDINGS = [
        ("f1", "next_model", "Cambia modello"),
        ("f2", "toggle_turbo", "Locale ↔ Turbo"),
        Binding("tab", "next_input_mode", "Modalità input", priority=True),
        Binding("ctrl+e", "external_editor", "Editor esterno", priority=True),
        ("ctrl+l", "clear_chat", "Pulisci chat"),
        ("f5", "toggle_mute", "Mute TTS"),
        Binding("f8", "stop_tts", "Stop voce", priority=True),
        Binding("ctrl+x", "stop_tts", "Stop voce", priority=True),
        Binding("escape", "stop_tts", "Stop voce", priority=True),
        ("ctrl+c", "quit", "Esci"),
    ]
    TITLE = "✦ Artefatto Magico — Cockpit"

    busy = reactive(False)
    muted = reactive(False)
    input_mode_idx = reactive(0)

    def __init__(self):
        super().__init__()
        self.client: Optional[ollama.Client] = None
        self.pool: Optional[PiperPool] = None
        self.alltalk = None  # EdgeTTSClient lazy
        self.fx = GpioFx() if GpioFx is not None else None
        self.db = Database(DB_PATH) if Database is not None else None
        self.session_id: Optional[int] = None
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.current_model = DEFAULT_MODEL
        self.use_turbo = False
        self.preset = PRESET_LOCAL
        self.turn_id = 0
        self.turbo_models: list[str] = []
        self.audio = AudioPlayer()
        # Sticky RAG context: tiene i match degli ultimi 2 turni per evitare
        # che il 3° turno perda il filo (multi-turn coherence).
        self.sticky = StickyContext(max_turns=2)

    # ------------------------------------------------------------------
    # Layout + lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "[b]F1[/b] modello  [b]F2[/b] turbo  [b]TAB[/b] modalità  "
            "[b]F5[/b] mute  [b]F8[/b]/[b]ESC[/b] stop  [b]Ctrl+L[/b] clear  "
            "[b]Ctrl+E[/b] editor  [b]Shift+Enter[/b] newline  "
            "[b]Ctrl+C[/b] esci  [b]/help[/b] comandi",
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
        if self.fx:
            self.fx.boot()
            self.fx.turbo(self.use_turbo)
        await asyncio.to_thread(self._init_engines)
        # Auto-switch a turbo all'avvio (configurabile via ARTEFATTO_START_TURBO).
        # Non logghiamo session.start finché non abbiamo il modello definitivo.
        if START_TURBO and TURBO_URL and not self.use_turbo:
            self.action_toggle_turbo()
        if self.db:
            self.session_id = self.db.start_session(
                model=self.current_model, turbo=self.use_turbo,
            )
        self.chat.add_sys(f"pronto · modello {self.current_model}")
        log_event("session.start", model=self.current_model, session_id=self.session_id)
        # Mostra subito il messaggio + libera la UI; il TTS parte in background
        # così l'utente può già scrivere senza aspettare che la voce finisca.
        widget = self.chat.add_art_start()
        widget.update(f"[b]◈[/b]   [i]{WAKE_LINE}[/i]")
        self.history.append({"role": "assistant", "content": WAKE_LINE})
        if self.db and self.session_id:
            self.db.log_message(self.session_id, "assistant", WAKE_LINE)
        self.set_busy(False)
        if not self.muted:
            asyncio.create_task(asyncio.to_thread(self._speak_one, WAKE_LINE))

    def _init_engines(self):
        self.client = ollama.Client()
        self.pool = PiperPool()
        self.pool.get(self.preset)
        # Sync col sito campagna.pignalabs.it (opzionale). Se SYNC_URL è
        # vuoto la funzione ritorna None e la TUI resta offline come prima.
        try:
            from sync import attach as _sync_attach
            self.sync = _sync_attach(self.db) if self.db else None
        except Exception as e:
            log_event("sync.attach_fail", err=repr(e))
            self.sync = None

    async def on_unmount(self):
        log_event("session.end", session_id=self.session_id)
        if getattr(self, "sync", None):
            try:
                self.sync.stop()
            except Exception:
                pass
        if self.fx:
            self.fx.shutdown()
            await asyncio.sleep(1.2)
            self.fx.close()
        if self.pool:
            self.pool.close_all()
        if self.db:
            if self.session_id:
                self.db.end_session(self.session_id)
            self.db.close()

    # ------------------------------------------------------------------
    # Stats / busy
    # ------------------------------------------------------------------

    def refresh_stats(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            temp_c = self._read_temp()
            self.status.cpu_bar.update_value(cpu, suffix="")
            self.status.ram_bar.update_value(ram, suffix="")
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

    def set_busy(self, busy: bool, msg: str = ""):
        self.busy = busy
        self.input.disabled = busy
        if busy:
            self.input.placeholder = f"⏳ {msg}" if msg else "⏳ in elaborazione…"
        else:
            _, title, _, placeholder = INPUT_MODES[self.input_mode_idx]
            self.input.placeholder = f"[{title}] {placeholder}"
            self.call_after_refresh(self.input.focus)

    # ------------------------------------------------------------------
    # Keybindings
    # ------------------------------------------------------------------

    def action_clear_chat(self):
        """Pulisce solo la chat visibile (history LLM e DB restano intatti)."""
        for child in list(self.chat.children):
            child.remove()
        self.chat.add_sys("chat pulita (storia LLM intatta)")
        if self.fx:
            self.fx.beep("short")

    def action_next_input_mode(self):
        if self.busy:
            return
        self.input_mode_idx = (self.input_mode_idx + 1) % len(INPUT_MODES)
        if self.fx:
            self.fx.beep("chirp")
            _, _, _, _ = INPUT_MODES[self.input_mode_idx]

    async def action_external_editor(self):
        """Apre $EDITOR (default nano) con il contenuto attuale dell'input.
        Alla chiusura, il contenuto del file viene messo nell'input come
        se fosse stato digitato — la modalità corrente (CODEX, LORE, ...)
        applica poi il suo prefisso normalmente al submit.
        """
        if self.busy:
            return
        import os, tempfile, subprocess
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.input.value)
            tmp_path = f.name
        try:
            with self.suspend():
                subprocess.run([editor, tmp_path], check=False)
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read().rstrip("\n")
            self.input.value = content
            self.input.cursor_position = len(content)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if self.fx:
            self.fx.beep("ack")

    def watch_input_mode_idx(self, idx: int):
        if not hasattr(self, "input"):
            return
        key, title, _color, placeholder = INPUT_MODES[idx]
        # Aggiorna classi CSS (rimuovo le altre, aggiungo la corrente)
        for k, _, _, _ in INPUT_MODES:
            self.input.remove_class(f"mode-{k}")
        self.input.add_class(f"mode-{key}")
        # Placeholder dinamico
        if not self.busy:
            self.input.placeholder = f"[{title}] {placeholder}"
        if hasattr(self, "chat"):
            self.chat.add_sys(f"modalità input → {title}")

    def action_toggle_mute(self):
        self.muted = not self.muted
        self.chat.add_sys(f"TTS {'MUTO' if self.muted else 'attivo'}")
        if self.fx:
            self.fx.beep("low" if self.muted else "ack")
            self.fx.flash("rosso" if self.muted else "verde", 0.3)

    def action_stop_tts(self):
        if self.fx:
            self.fx.idle("bianco")
        killed = self.audio.stop_all()
        self.chat.add_sys(f"voce interrotta ({killed} traccia/e)")

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
        if self.fx:
            self.fx.beep("short")
            self.fx.flash("viola", 0.25)

    def action_toggle_turbo(self):
        if self.busy:
            return
        if not TURBO_URL:
            self.chat.add_sys("turbo non configurato (manca OLLAMA_TURBO_URL)")
            return
        self.use_turbo = not self.use_turbo
        if self.use_turbo:
            if TURBO_BACKEND == "openai":
                # LM Studio (OpenAI-compatible). URL deve includere /v1 oppure
                # lo aggiungiamo noi se manca.
                base = TURBO_URL.rstrip("/")
                if not base.endswith("/v1"):
                    base = base + "/v1"
                self.client = OpenAIClient(base_url=base)
            else:
                self.client = ollama.Client(host=TURBO_URL)
            if not self.turbo_models:
                self.turbo_models = self._discover_turbo_models()
            self.current_model = self.turbo_models[0] if self.turbo_models else TURBO_MODEL
            self.preset = PRESET_TURBO
            if EDGE_TTS_ENABLED and AllTalkClient is not None:
                try:
                    if self.alltalk is None:
                        self.alltalk = AllTalkClient(voice=EDGE_TTS_VOICE, rate=EDGE_TTS_RATE)
                    if self.alltalk.is_ready(timeout=2.0):
                        self.chat.add_sys(f"TTS remoto attivo · {EDGE_TTS_VOICE}")
                    else:
                        self.chat.add_sys("TTS remoto NON raggiungibile · uso Piper")
                        self.alltalk = None
                except Exception as e:
                    log_event("edge_tts.init_error", err=repr(e))
                    self.alltalk = None
            self.status.host_label = f"⚡ turbo ({TURBO_URL})"
        else:
            self.client = ollama.Client()
            self.current_model = DEFAULT_MODEL
            self.preset = PRESET_LOCAL
            self.status.host_label = "locale (Pi)"
        if self.pool:
            asyncio.get_running_loop().run_in_executor(None, lambda: self.pool.get(self.preset))
        self.status.model = self.current_model
        voice_label = EDGE_TTS_VOICE if (self.use_turbo and self.alltalk is not None) \
            else self.preset["voice"].split("-")[1]
        self.chat.add_sys(f"host → {self.status.host_label} · voce {voice_label}")
        log_event("host.switch", turbo=self.use_turbo, model=self.current_model)
        if self.fx:
            self.fx.beep("double")
            self.fx.flash("arancio" if self.use_turbo else "azzurro", 0.3)
            self.fx.turbo(self.use_turbo)

    def _discover_turbo_models(self) -> list[str]:
        if TURBO_MODELS_ENV:
            return [m.strip() for m in TURBO_MODELS_ENV.split(",") if m.strip()]
        try:
            import urllib.request, json
            base = TURBO_URL.rstrip("/")
            if TURBO_BACKEND == "openai":
                # LM Studio: endpoint OpenAI /v1/models, formato diverso
                url = base + ("/v1/models" if not base.endswith("/v1") else "/models")
                with urllib.request.urlopen(url, timeout=5) as r:
                    data = json.loads(r.read())
                names = [m["id"] for m in data.get("data", [])]
            else:
                with urllib.request.urlopen(f"{base}/api/tags", timeout=5) as r:
                    data = json.loads(r.read())
                names = [m["name"] for m in data.get("models", [])]
            if TURBO_MODEL in names:
                names.remove(TURBO_MODEL)
                names.insert(0, TURBO_MODEL)
            return names or [TURBO_MODEL]
        except Exception as e:
            log_event("turbo.discover.error", err=repr(e))
            return [TURBO_MODEL]

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

        # Modalità input: se non sei in "libera" e non hai scritto uno slash
        # esplicito, traduco l'input nel comando della modalità corrente.
        mode_key = INPUT_MODES[self.input_mode_idx][0]
        if mode_key != "libera" and not text.startswith("/"):
            prefix_map = {
                "codex": "/codex add ",
                "roll":  "/roll ",
                "lore":  "/lore add ",
            }
            text = prefix_map[mode_key] + text

        if text.startswith("/"):
            self.chat.add_user(text)
            if await handle_slash(self, text):
                return

        self.chat.add_user(text)
        if self.db and self.session_id:
            self.db.log_message(self.session_id, "user", text)
        self.set_busy(True, "l'artefatto pensa…")
        sentences, full_text = await self._llm_phase(text)
        self.set_busy(False)
        if sentences and not self.muted:
            asyncio.create_task(self._speak_phase(sentences, full_text))

    async def _llm_phase(self, user_text: str) -> tuple[list[str], str]:
        if self.fx:
            self.fx.thinking()
        self.history.append({"role": "user", "content": user_text})
        widget = self.chat.add_art_start()
        self.turn_id += 1
        turn = self.turn_id

        messages, lore_matches, codex_matches, _, _ = build_messages_with_rag(
            self.history, user_text, self.db, sticky=self.sticky,
        )
        if lore_matches or codex_matches:
            lore_names = ",".join(m.name for m in lore_matches) or "-"
            codex_titles = ",".join(m.title for m in codex_matches) or "-"
            self.chat.add_sys(f"RAG: lore=[{lore_names}] codex=[{codex_titles}]")

        kw = chat_kwargs(self.current_model, messages)
        full_text = ""
        sentences: list[str] = []
        buffer = ""
        t_start = time.perf_counter()
        t_first = None
        n_tokens = 0

        async for chunk in stream_chat(self.client, kw):
            if "_error" in chunk:
                self.chat.add_sys(f"errore LLM: {chunk['_error']}")
                self.history.pop()
                if self.fx:
                    self.fx.error()
                    self.fx.beep("deny")
                return [], ""
            tok = (chunk.get("message", {}) or {}).get("content", "") or ""
            if not tok:
                continue
            if t_first is None:
                t_first = time.perf_counter() - t_start
            n_tokens += 1
            if self.fx and n_tokens % 12 == 0:
                self.fx.flash(random.choice(("giallo", "viola")), 0.08)
            full_text += tok
            buffer += tok
            widget.update(f"[b]◈[/b]   [i]{full_text}[/i]")
            self.chat.scroll_end(animate=False)
            new_sentences, buffer = split_sentences(buffer)
            sentences.extend(new_sentences)

        if buffer.strip():
            sentences.append(buffer.strip())

        t_llm = time.perf_counter() - t_start
        tps = n_tokens / t_llm if t_llm else 0
        self.status.last_ttok = f"{tps:.1f} tok/s · {n_tokens}t in {t_llm:.1f}s"
        log_event("llm.stream", turn=turn, model=self.current_model,
                  ttft_s=f"{(t_first or 0):.2f}", total_s=f"{t_llm:.2f}",
                  tokens=n_tokens, tok_per_s=f"{tps:.2f}", chars=len(full_text))
        sample = full_text[:200].replace("\n", " ")
        log_event("llm.reply", turn=turn, sample=f'"{sample}"')
        self.history.append({"role": "assistant", "content": full_text})
        if self.db and self.session_id:
            self.db.log_message(self.session_id, "assistant", full_text,
                                model=self.current_model, tokens=n_tokens,
                                duration_s=t_llm)
        return sentences, full_text

    async def _speak_phase(self, sentences: list[str], full_text: str):
        self.audio.reset()
        if self.fx:
            self.fx.speaking()
        t_start = time.perf_counter()

        if self.use_turbo and self.alltalk is not None and full_text.strip():
            await asyncio.to_thread(self._speak_one, full_text)
        else:
            for s in sentences:
                if self.audio.stop_flag:
                    break
                await asyncio.to_thread(self._speak_one, s)

        if self.fx:
            self.fx.idle("bianco")
        log_event("speak.end", total_s=f"{time.perf_counter() - t_start:.2f}",
                  chars=len(full_text), stopped=self.audio.stop_flag,
                  mode="turbo_single" if self.use_turbo and self.alltalk else "local_split")

    def _speak_one(self, text: str):
        try:
            if self.audio.stop_flag:
                return
            text = consume_tags(text, self.fx)
            text = sanitize_for_tts(text)
            if not text.strip():
                return
            t0 = time.perf_counter()
            raw = self._synth_text(text)
            t_piper = time.perf_counter() - t0
            t0 = time.perf_counter()
            fx_wav = apply_sox(raw, self.preset["effects"])
            t_sox = time.perf_counter() - t0
            log_event("tts.synth", chars=len(text),
                      piper_s=f"{t_piper:.2f}", sox_s=f"{t_sox:.2f}")
            if self.audio.stop_flag:
                raw.unlink(missing_ok=True)
                fx_wav.unlink(missing_ok=True)
                return
            dur = self.audio.play_blocking(fx_wav)
            log_event("audio.play", duration_s=f"{dur:.2f}")
            raw.unlink(missing_ok=True)
            fx_wav.unlink(missing_ok=True)
        except Exception as e:
            log_event("tts.error", err=repr(e))
            if self.fx:
                self.fx.error()
                self.fx.beep("deny")

    def _synth_text(self, text: str) -> Path:
        """Sintetizza una frase con il backend attivo (edge-tts in turbo,
        Piper altrimenti). Fallback a Piper se edge-tts fallisce."""
        if self.use_turbo and self.alltalk is not None:
            try:
                return self.alltalk.synth(text)
            except Exception as e:
                log_event("alltalk.error", err=repr(e))
        return self.pool.get(self.preset).synth(text)

    async def speak_and_show(self, text: str):
        widget = self.chat.add_art_start()
        widget.update(f"[b]◈[/b]   [i]{text}[/i]")
        if not self.muted:
            await asyncio.to_thread(self._speak_one, text)


def main():
    ArtefattoApp().run()


if __name__ == "__main__":
    main()
