"""Sync col sito campagna.pignalabs.it.

- All'avvio: GET delta dall'ultima sync e fa merge nel SQLite locale.
- A regime: connessione WebSocket persistente con autoreconnect.
- Su write locali (callback `db.on_write`): emette via WS o accoda su
  `data/sync_queue.jsonl` se offline. Flush della coda al riconnect.

Se ARTEFATTO_SYNC_URL è vuoto, l'intero modulo è no-op: `attach()` ritorna
senza fare nulla. La TUI continua a funzionare offline come prima.

Implementazione: HTTP via stdlib urllib (no nuove deps obbligatorie).
WebSocket usa `websocket-client` solo se installato; altrimenti fallback
a polling HTTP ogni `SYNC_PULL_INTERVAL` secondi.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from config import (
    DATA_DIR, PI_SYNC_KEY, SYNC_PULL_INTERVAL, SYNC_URL, log_event,
)


QUEUE_PATH = DATA_DIR / "sync_queue.jsonl"
STATE_PATH = DATA_DIR / "sync_state.json"


class SyncClient:
    """Client di sync tra il Pi (SQLite locale) e il sito (Postgres remoto).

    Uso tipico:
        sync = SyncClient(db, base_url, api_key)
        sync.start()    # thread daemon che pulla e mantiene la connessione

    Il `db.on_write` viene impostato esternamente per puntare a `sync.push`.
    """

    def __init__(self, db, base_url: str, api_key: str,
                 pull_interval: int = SYNC_PULL_INTERVAL):
        self.db = db
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.pull_interval = max(15, pull_interval)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ws = None
        self._ws_thread: Optional[threading.Thread] = None
        QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self):
        """Avvia il sync in background. Non blocca."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="sync-loop", daemon=True,
        )
        self._thread.start()
        log_event("sync.start", url=self.base, interval=self.pull_interval)

    def stop(self):
        self._stop.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass

    def status(self) -> str:
        """Stringa breve per la status bar: ws|http|off + coda pendente."""
        pending = 0
        try:
            if QUEUE_PATH.exists():
                with QUEUE_PATH.open("r", encoding="utf-8") as f:
                    pending = sum(1 for line in f if line.strip())
        except Exception:
            pass
        connected = (
            self._ws is not None and getattr(self._ws, "sock", None) is not None
        )
        base = "ws✓" if connected else "http"
        if pending:
            return f"sync: {base} (q={pending})"
        return f"sync: {base}"

    def push(self, table: str, op: str, payload: dict):
        """Callback per `db.on_write`. Emette via WS se connesso, altrimenti
        accoda. Non solleva mai: una write locale deve sempre andare a
        buon fine anche se il sync è giù."""
        msg = {"table": table, "op": op, "payload": payload, "ts": time.time()}
        if self._ws_send(msg):
            return
        self._enqueue(msg)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def _run(self):
        # Pull iniziale (bootstrap), poi loop di pull periodico + flush queue.
        try:
            self._pull_delta()
        except Exception as e:
            log_event("sync.pull.bootstrap_error", err=repr(e))
        # Prova WS
        self._maybe_connect_ws()
        # Loop principale: ogni N secondi rifa il pull (anche con WS attivo,
        # come safety net) e prova a flushare la coda.
        while not self._stop.wait(self.pull_interval):
            try:
                self._pull_delta()
            except Exception as e:
                log_event("sync.pull.error", err=repr(e))
            self._flush_queue()
            if self._ws is None:
                self._maybe_connect_ws()

    # ------------------------------------------------------------------
    # HTTP pull (delta)
    # ------------------------------------------------------------------
    def _pull_delta(self):
        since = self._load_last_pull()
        for table in ("lore", "codex"):
            try:
                rows = self._http_get(
                    f"/api/sync/{table}?since={urllib.request.quote(since or '')}"
                )
            except Exception as e:
                log_event("sync.pull.fail", table=table, err=repr(e))
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                self._apply_remote(table, row)
            log_event("sync.pull.ok", table=table, n=len(rows))
        self._save_last_pull(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def _apply_remote(self, table: str, row: dict):
        if table == "lore":
            self.db.merge_lore_from_remote(row)
        elif table == "codex":
            self.db.merge_codex_from_remote(row)

    # ------------------------------------------------------------------
    # Offline queue
    # ------------------------------------------------------------------
    def _enqueue(self, msg: dict):
        try:
            with QUEUE_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        except Exception as e:
            log_event("sync.queue.error", err=repr(e))

    def _flush_queue(self):
        if not QUEUE_PATH.exists():
            return
        pending = []
        try:
            with QUEUE_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        pending.append(json.loads(line))
                    except Exception:
                        pass
        except Exception:
            return
        if not pending:
            QUEUE_PATH.unlink(missing_ok=True)
            return
        leftover: list[dict] = []
        for msg in pending:
            ok = False
            try:
                ok = self._ws_send(msg) or self._http_push(msg)
            except Exception:
                ok = False
            if not ok:
                leftover.append(msg)
        if leftover:
            with QUEUE_PATH.open("w", encoding="utf-8") as f:
                for m in leftover:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
        else:
            QUEUE_PATH.unlink(missing_ok=True)
        log_event("sync.flush", flushed=len(pending) - len(leftover),
                  remaining=len(leftover))

    # ------------------------------------------------------------------
    # WebSocket (opzionale, richiede websocket-client)
    # ------------------------------------------------------------------
    def _maybe_connect_ws(self):
        # Il sito usa Socket.io, non WebSocket puro: servirebbe python-socketio
        # come client. Per ora ci limitiamo al polling HTTP (sufficiente per
        # uso single-user). Se python-socketio è installato, in futuro
        # potremmo collegare il client qui.
        try:
            import socketio  # type: ignore  # noqa: F401
        except Exception:
            return
        # TODO: implementare client socketio quando serve push real-time
        return
        # Codice legacy non eseguito ma tenuto come riferimento:
        try:
            import websocket  # type: ignore
        except Exception:
            return
        ws_url = self.base.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/sync"

        def on_open(ws):
            log_event("sync.ws.open")
            self._flush_queue()

        def on_message(ws, raw):
            try:
                msg = json.loads(raw)
            except Exception:
                return
            table = msg.get("table")
            row = msg.get("payload") or {}
            if table in ("lore", "codex"):
                self._apply_remote(table, row)

        def on_close(ws, *_):
            log_event("sync.ws.close")
            self._ws = None

        def on_error(ws, err):
            log_event("sync.ws.error", err=repr(err))

        try:
            self._ws = websocket.WebSocketApp(
                ws_url,
                header=[f"X-Pi-Key: {self.key}"],
                on_open=on_open, on_message=on_message,
                on_close=on_close, on_error=on_error,
            )
            self._ws_thread = threading.Thread(
                target=self._ws.run_forever,
                kwargs={"ping_interval": 25, "ping_timeout": 10},
                name="sync-ws", daemon=True,
            )
            self._ws_thread.start()
        except Exception as e:
            log_event("sync.ws.start_fail", err=repr(e))
            self._ws = None

    def _ws_send(self, msg: dict) -> bool:
        if self._ws is None or not getattr(self._ws, "sock", None):
            return False
        try:
            self._ws.send(json.dumps(msg, ensure_ascii=False))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _http_get(self, path: str):
        req = urllib.request.Request(
            f"{self.base}{path}",
            headers={"X-Pi-Key": self.key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _http_push(self, msg: dict) -> bool:
        path = f"/api/sync/{msg['table']}"
        body = json.dumps({"op": msg["op"], "payload": msg["payload"]}).encode()
        req = urllib.request.Request(
            f"{self.base}{path}", data=body, method="POST",
            headers={
                "X-Pi-Key": self.key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as e:
            # 409 conflict = server vince, applico la risposta come merge.
            if e.code == 409:
                try:
                    server_row = json.loads(e.read().decode("utf-8"))
                    self._apply_remote(msg["table"], server_row)
                    return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Persistenza ultimo timestamp di pull
    # ------------------------------------------------------------------
    def _load_last_pull(self) -> str:
        if not STATE_PATH.exists():
            return ""
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8")).get("last_pull", "")
        except Exception:
            return ""

    def _save_last_pull(self, ts: str):
        try:
            STATE_PATH.write_text(
                json.dumps({"last_pull": ts}), encoding="utf-8",
            )
        except Exception:
            pass


def attach(db) -> Optional[SyncClient]:
    """Crea e avvia un SyncClient se configurato; altrimenti no-op.

    Aggancia `db.on_write = sync.push` così ogni write locale finisce nel
    sito. Ritorna l'istanza (per stop in shutdown) o None se disabilitato.
    """
    if not SYNC_URL or not PI_SYNC_KEY:
        log_event("sync.disabled", reason="missing_env")
        return None
    sync = SyncClient(db, SYNC_URL, PI_SYNC_KEY)
    db.on_write = sync.push
    sync.start()
    return sync
