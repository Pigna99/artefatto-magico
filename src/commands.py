"""Slash commands: /lore, /codex, /roll, /help.

Le funzioni ricevono l'istanza `app` (ArtefattoApp) per accedere a db, fx, chat.
Ritornano True se il comando è stato gestito (non va all'LLM).
"""
from __future__ import annotations

import random
import re


HELP_TEXT = (
    "comandi: /codex list · /codex edit <titolo> · /codex rm <titolo> · "
    "/roll <nDx> (es. /roll d20, /roll 2d6). "
    "TAB → CODEX: scrivi il titolo (Invio apre l'editor, "
    "se il titolo esiste già viene caricato per la modifica)."
)


async def handle_slash(app, text: str) -> bool:
    """Routing principale. Ritorna sempre True (qualunque comando è 'gestito',
    incluso 'ignoto')."""
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # /roll non richiede DB
    if cmd in ("/roll", "/r", "/dice", "/d"):
        return _cmd_roll(app, rest)

    if app.db is None:
        app.chat.add_sys("DB non disponibile, comandi /lore disabilitati")
        return True

    try:
        if cmd in ("/lore", "/l"):
            return _cmd_lore(app, rest)
        if cmd in ("/codex", "/c"):
            return _cmd_codex(app, rest)
        if cmd == "/help":
            app.chat.add_sys(HELP_TEXT)
            return True
        app.chat.add_sys(f"comando ignoto: {cmd} (prova /help)")
        return True
    except Exception as e:
        app.chat.add_sys(f"errore comando: {e}")
        return True


def _cmd_roll(app, rest: str) -> bool:
    """Tira nDx (default d20). FX visivo+sonoro in base al risultato."""
    spec = (rest or "d20").strip().lower().replace(" ", "")
    m = re.match(r"^(\d*)d(\d+)$", spec)
    if not m:
        app.chat.add_sys("sintassi: /roll d20 oppure /roll 2d6")
        return True
    n = int(m.group(1) or "1")
    sides = int(m.group(2))
    if n < 1 or n > 20 or sides < 2 or sides > 1000:
        app.chat.add_sys("intervallo: 1≤n≤20, 2≤d≤1000")
        return True
    rolls = [random.randint(1, sides) for _ in range(n)]
    total = sum(rolls)
    detail = " + ".join(str(r) for r in rolls)
    app.chat.add_sys(f"🎲 {spec}: {detail}{' = ' + str(total) if n > 1 else ''}")
    if app.fx:
        app.fx.beep("dice")
        if n == 1 and sides == 20:
            if total == 20:
                app.fx.flash("giallo", 1.0)
            elif total == 1:
                app.fx.flash("rosso", 1.0)
            elif total >= 15:
                app.fx.flash("verde", 0.8)
            elif total >= 8:
                app.fx.flash("arancio", 0.5)
            else:
                app.fx.flash("rosso", 0.5)
        else:
            app.fx.flash("viola", 0.5)
    return True


def _cmd_lore(app, rest: str) -> bool:
    """/lore list|search. Read-only: il Pi non scrive piu' lore (le voci
    vengono create dal GM sul sito campagna.pignalabs.it/lore/new).
    kind ∈ {npc,pg,place,item,event,note}"""
    if not rest:
        app.chat.add_sys(
            "uso: /lore list [kind] · /lore search <query>. "
            "Per aggiungere voci: campagna.pignalabs.it/lore/new (solo GM)."
        )
        return True
    sub, _, args = rest.partition(" ")
    sub = sub.lower()

    if sub == "list":
        entries = app.db.all_lore()
        if args.strip():
            entries = [e for e in entries if e.kind == args.strip()]
        if not entries:
            app.chat.add_sys("lore vuoto")
        else:
            for e in entries[:30]:
                app.chat.add_sys(e.to_context_line())
            if len(entries) > 30:
                app.chat.add_sys(f"...e altri {len(entries)-30}")
    elif sub == "search":
        q = args.strip()
        if not q:
            app.chat.add_sys("uso: /lore search <query>")
            return True
        entries = app.db.search_lore(q, limit=10)
        if not entries:
            app.chat.add_sys(f"nessun match per '{q}'")
        else:
            for e in entries:
                app.chat.add_sys(e.to_context_line())
    elif sub in ("add", "rm", "edit", "delete"):
        app.chat.add_sys(
            f"/lore {sub} disabilitato: il Pi e' read-only. "
            "Usa campagna.pignalabs.it/lore (solo GM puo' modificare)."
        )
    else:
        app.chat.add_sys(f"sotto-comando ignoto: /lore {sub} (prova list|search)")
    return True


def _cmd_codex(app, rest: str) -> bool:
    """/codex add|append|list|rm"""
    if not rest:
        app.chat.add_sys("uso: /codex add|append|list|rm ...")
        return True
    sub, _, args = rest.partition(" ")
    sub = sub.lower()

    if sub == "add":
        tokens = args.split(maxsplit=1)
        if len(tokens) < 2:
            app.chat.add_sys("uso: /codex add <titolo> <testo>")
            return True
        title, body = tokens
        app.db.add_codex(title=title, body=body)
        app.chat.add_sys(f"codex salvato: {title}")
    elif sub == "append":
        tokens = args.split(maxsplit=1)
        if len(tokens) < 2:
            app.chat.add_sys("uso: /codex append <titolo> <testo>")
            return True
        title, body = tokens
        app.db.append_codex(title, body)
        app.chat.add_sys(f"codex esteso: {title}")
    elif sub == "list":
        entries = app.db.all_codex(limit=30)
        if not entries:
            app.chat.add_sys("codex vuoto")
        else:
            for e in entries:
                app.chat.add_sys(e.to_context_line())
    elif sub == "rm":
        title = args.strip()
        if not title:
            app.chat.add_sys("uso: /codex rm <titolo>")
            return True
        n = app.db.remove_codex(title)
        app.chat.add_sys(f"rimosso {n} elementi")
    elif sub == "edit":
        title = args.strip()
        if not title:
            app.chat.add_sys("uso: /codex edit <titolo>")
            return True
        # Riuso il flow CODEX two-step (apre editor con body precaricato).
        import asyncio
        asyncio.create_task(app._codex_two_step(title=title))
    else:
        app.chat.add_sys(f"sotto-comando ignoto: /codex {sub}")
    return True
