"""Widgets Textual: StatBar, StatusPanel, HistoryInput, ChatLog."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Label, ProgressBar, Static


class StatBar(Static):
    """Barra colorata con etichetta, valore, percentuale."""

    DEFAULT_CSS = """
    StatBar { height: 2; padding: 0; layout: vertical; }
    StatBar Label { color: $text-muted; height: 1; }
    StatBar ProgressBar { width: 1fr; height: 1; }
    StatBar Bar { height: 1; }
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
    """Pannello in cima: barre CPU/RAM/TEMP + modello/host/ultimo turno."""

    DEFAULT_CSS = """
    StatusPanel { height: 9; padding: 0 1; border: round $primary; }
    StatusPanel > .col { width: 1fr; padding: 0 1; }
    StatusPanel Static.title { color: $accent; text-style: bold; height: 1; }
    StatusPanel Label { color: $text-muted; }
    .ok ProgressBar > Bar > .bar--bar { color: $success; }
    .warn ProgressBar > Bar > .bar--bar { color: $warning; }
    .crit ProgressBar > Bar > .bar--bar { color: $error; }
    """

    model = reactive("--")
    host_label = reactive("locale (Pi)")
    last_ttok = reactive("--")

    def compose(self) -> ComposeResult:
        with Vertical(classes="col"):
            yield Static("◆ RISORSE", classes="title")
            self.cpu_bar = StatBar("CPU ", warn=0.6, crit=0.85)
            self.ram_bar = StatBar("RAM ", warn=0.7, crit=0.9)
            self.temp_bar = StatBar("TEMP", warn=0.65, crit=0.85)
            yield self.cpu_bar
            yield self.ram_bar
            yield self.temp_bar
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
    """Input con history navigabile con ↑/↓."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history: list[str] = []
        self.h_index: int = 0
        self._draft: str = ""

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
