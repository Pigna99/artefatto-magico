"""Wrapper streaming Ollama + iniezione RAG (lore + codex).

Espone `stream_chat()` come async-generator di chunk pronti da gestire
nella TUI. Mantiene la logica RAG centralizzata.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from config import log_event


def build_messages_with_rag(history: list[dict], user_text: str, db) -> tuple[list[dict], list, list, str, str]:
    """Compone i messaggi da inviare a Ollama. Itera RAG su lore + codex e
    li inserisce come system message AGGIUNTIVO (non li mette in history).

    Ritorna (messages, lore_matches, codex_matches, ctx_lore, ctx_codex).
    """
    if db is None:
        return history, [], [], "", ""

    codex_matches = db.search_codex(user_text)
    ctx_codex = db.codex_context_for(user_text)
    # Quando c'è codex riduciamo le voci lore a 3 (era 1 prima, troppo
    # aggressivo: rischiava di scartare il match più rilevante). Con il fix
    # name-boost in search_lore, anche 3 voci tengono la lore giusta in cima.
    lore_limit = 3 if codex_matches else 5
    lore_matches = db.search_lore(user_text, limit=lore_limit)
    ctx_lore = db.lore_context_for(user_text, max_entries=lore_limit)
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
