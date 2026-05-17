"""Slash commands: /lore, /codex, /roll, /help.

Le funzioni ricevono l'istanza `app` (ArtefattoApp) per accedere a db, fx, chat.
Ritornano True se il comando è stato gestito (non va all'LLM).
"""
from __future__ import annotations

import random
import re


HELP_TEXT = (
    "comandi: /lore add <kind> <name> <description> · /lore list · /lore rm <name> · "
    "/codex add <title> <body> · /codex append <title> <body> · /codex list · /codex rm <title> · "
    "/roll <nDx> (es. /roll d20, /roll 2d6)"
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
    """/lore add|list|rm. kind ∈ {npc,pg,place,item,event,note}"""
    if not rest:
        app.chat.add_sys("uso: /lore add|list|rm ...")
        return True
    sub, _, args = rest.partition(" ")
    sub = sub.lower()

    if sub == "add":
        tokens = args.split(maxsplit=2)
        if len(tokens) < 3:
            app.chat.add_sys("uso: /lore add <kind> <name> <description>")
            return True
        kind, name, desc = tokens
        app.db.add_lore(name=name, kind=kind, description=desc)
        app.chat.add_sys(f"lore salvato: {kind} {name}")
    elif sub == "list":
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
    elif sub == "rm":
        tokens = args.split(maxsplit=1)
        if not tokens:
            app.chat.add_sys("uso: /lore rm <name> [kind]")
            return True
        name = tokens[0]
        kind = tokens[1] if len(tokens) > 1 else None
        n = app.db.remove_lore(name, kind)
        app.chat.add_sys(f"rimosso {n} elementi")
    else:
        app.chat.add_sys(f"sotto-comando ignoto: /lore {sub}")
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
    else:
        app.chat.add_sys(f"sotto-comando ignoto: /codex {sub}")
    return True
