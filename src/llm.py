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

    lore_matches = db.search_lore(user_text)
    codex_matches = db.search_codex(user_text)
    ctx_lore = db.lore_context_for(user_text)
    ctx_codex = db.codex_context_for(user_text)
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
    """Wrap streaming Ollama come async-iterable. Cattura eccezioni come
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
