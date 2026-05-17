"""Wrapper streaming Ollama + iniezione RAG (lore + codex).

Espone `stream_chat()` come async-generator di chunk pronti da gestire
nella TUI. Mantiene la logica RAG centralizzata.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from config import log_event


class StickyContext:
    """Mantiene gli ultimi N turni di matches RAG così che le voci viste
    nei turni precedenti restino nel contesto anche se il turno corrente
    non matcha le stesse keyword.

    Utile per conversazioni multi-turn dove il 3° turno usa pronomi/parole
    diverse che non aggancerebbero il RAG sul tema del turno 1.
    """

    def __init__(self, max_turns: int = 2):
        self.max_turns = max_turns
        self._lore_per_turn: list[list] = []
        self._codex_per_turn: list[list] = []

    def add_turn(self, lore_matches: list, codex_matches: list):
        self._lore_per_turn.append(lore_matches)
        self._codex_per_turn.append(codex_matches)
        # Tieni solo gli ultimi max_turns
        self._lore_per_turn = self._lore_per_turn[-self.max_turns:]
        self._codex_per_turn = self._codex_per_turn[-self.max_turns:]

    def recent_lore(self) -> list:
        """Tutte le voci uniche degli ultimi N turni (più recenti per primi)."""
        seen = set()
        out = []
        for turn in reversed(self._lore_per_turn):
            for l in turn:
                if l.id not in seen:
                    out.append(l)
                    seen.add(l.id)
        return out

    def recent_codex(self) -> list:
        seen = set()
        out = []
        for turn in reversed(self._codex_per_turn):
            for c in turn:
                if c.id not in seen:
                    out.append(c)
                    seen.add(c.id)
        return out


def build_messages_with_rag(history: list[dict], user_text: str, db,
                             sticky: Optional["StickyContext"] = None
                             ) -> tuple[list[dict], list, list, str, str]:
    """Compone i messaggi da inviare al modello. Itera RAG su lore + codex e
    li inserisce come system message AGGIUNTIVO (non li mette in history).

    Se `sticky` è fornito, le voci di lore/codex matchate nei turni precedenti
    vengono mantenute nel contesto per N turni — utile per multi-turn
    coerente (il 3° turno spesso non matcha le keyword dei primi due).

    Ritorna (messages, lore_matches, codex_matches, ctx_lore, ctx_codex).
    """
    if db is None:
        return history, [], [], "", ""

    codex_matches = list(db.search_codex(user_text))
    # Quando c'è codex riduciamo le voci lore a 3 (era 1 prima, troppo
    # aggressivo: rischiava di scartare il match più rilevante). Con il fix
    # name-boost in search_lore, anche 3 voci tengono la lore giusta in cima.
    lore_limit = 3 if codex_matches else 5
    lore_matches = list(db.search_lore(user_text, limit=lore_limit))

    # Sticky: aggiungi le voci viste nei turni precedenti (deduplicate)
    if sticky is not None:
        seen_lore_ids = {l.id for l in lore_matches}
        seen_codex_ids = {c.id for c in codex_matches}
        for l in sticky.recent_lore():
            if l.id not in seen_lore_ids:
                lore_matches.append(l)
                seen_lore_ids.add(l.id)
        for c in sticky.recent_codex():
            if c.id not in seen_codex_ids:
                codex_matches.append(c)
                seen_codex_ids.add(c.id)
        sticky.add_turn(lore_matches[:lore_limit], codex_matches[:5])

    # Ricostruisco i blocchi testo dalle liste finali (no doppia query DB)
    ctx_codex = ""
    if codex_matches:
        lines = [m.to_context_line() for m in codex_matches[:5]]
        ctx_codex = (
            "\n\nMEMORIA NARRATIVA (eventi realmente accaduti nelle "
            "sessioni passate; sono la VERITÀ vissuta da Pigna e prevalgono "
            "sul lore generale quando la domanda è 'cosa è successo', "
            "'ultimo', 'recente', 'dove siamo stati'):\n" + "\n".join(lines)
        )
    ctx_lore = ""
    if lore_matches:
        lines = [m.to_context_line() for m in lore_matches[:lore_limit + 2]]  # +2 sticky
        ctx_lore = (
            "\n\nCONTESTO RILEVANTE (lore della campagna, usa questo "
            "sapere se pertinente):\n" + "\n".join(lines)
        )
    # Mettiamo PRIMA il codex (memoria narrativa recente, prevale sul lore
    # quando la domanda è temporale tipo "ultimo", "recente", "ieri"...)
    # e DOPO il lore generale. I modelli pesano di più ciò che vedono prima.
    ctx = ctx_codex + ctx_lore

    if ctx:
        messages = (
            [history[0]]
            + [{"role": "system", "content": ctx.strip()}]
            + history[1:]
        )
        lore_names = ",".join(m.name for m in lore_matches) or "-"
        codex_titles = ",".join(m.title for m in codex_matches) or "-"
        log_event("rag.injected",
                  query=user_text[:80].replace(" ", "_"),
                  lore_n=len(lore_matches), codex_n=len(codex_matches),
                  lore_names=f"[{lore_names}]",
                  codex_titles=f"[{codex_titles}]",
                  lore_chars=len(ctx_lore), codex_chars=len(ctx_codex))
    else:
        messages = history
        log_event("rag.empty", query=user_text[:80].replace(" ", "_"))

    return messages, lore_matches, codex_matches, ctx_lore, ctx_codex


def chat_kwargs(model: str, messages: list[dict]) -> dict:
    """Costruisce i kwargs per ollama.Client.chat(), gestendo le specificità
    di qwen3 (think=False per disabilitare il reasoning nascosto)."""
    kw = {"model": model, "messages": messages, "stream": True}
    if "qwen3" in model.lower():
        kw["think"] = False
    return kw


async def stream_chat(client, kwargs: dict) -> AsyncIterator[dict]:
    """Wrap streaming come async-iterable. Cattura eccezioni come
    chunk speciale {'_error': ...} per non far esplodere il chiamante."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def producer():
        try:
            for chunk in client.chat(**kwargs):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, {"_error": repr(e)})
        loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(None, producer)
    while True:
        chunk = await queue.get()
        if chunk is None:
            return
        yield chunk


class OpenAIClient:
    """Client minimale che imita l'API di ollama.Client.chat() ma parla
    OpenAI-compatible endpoint (LM Studio, vLLM, ecc.).

    Espone solo chat(model, messages, stream, **) per essere drop-in
    sostituibile a ollama.Client nel resto del codice.
    """

    def __init__(self, base_url: str, api_key: str = "lm-studio"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def chat(self, *, model: str, messages: list[dict], stream: bool = True,
             think: Optional[bool] = None, **kwargs):
        """Mimics ollama.chat() output schema:
        - stream=True: yield {'message': {'content': tok}}
        - stream=False: return {'message': {'content': full_text}}
        Il param `think` di qwen3 è ignorato (l'OpenAI API standard non lo
        supporta; LM Studio ha le sue impostazioni nel preset del modello).
        """
        import urllib.request, json
        body = {"model": model, "messages": messages, "stream": stream}
        # Inoltro eventuali parametri OpenAI noti
        for k in ("temperature", "top_p", "max_tokens", "stop"):
            if k in kwargs:
                body[k] = kwargs[k]
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        if not stream:
            resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
            content = resp["choices"][0]["message"].get("content", "") or ""
            return {"message": {"content": content}}

        # Streaming SSE
        def _iter():
            with urllib.request.urlopen(req, timeout=180) as r:
                for line in r:
                    line = line.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                    except Exception:
                        continue
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    tok = delta.get("content", "")
                    if tok:
                        yield {"message": {"content": tok}}
        return _iter()
