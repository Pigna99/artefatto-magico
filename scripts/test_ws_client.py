"""Client Socket.io minimale per debug."""
import os, sys, time, threading
import socketio

URL = os.environ.get("ARTEFATTO_SYNC_URL", "https://campagna.pignalabs.it")
KEY = os.environ.get("ARTEFATTO_PI_SYNC_KEY", "")

if not KEY:
    print("ERR: KEY missing"); sys.exit(1)

received = []
sio = socketio.Client(logger=True, engineio_logger=True)


@sio.event
def connect():
    print(f"==> CONNECTED sid={sio.sid}", flush=True)


@sio.event
def disconnect():
    print(f"==> DISCONNECTED reason={sio.reason}" if hasattr(sio, "reason") else "==> DISCONNECTED", flush=True)


@sio.on("master.command")
def h1(data):
    print(f"==> HIT master.command {data}", flush=True)
    received.append(("dot", data))


@sio.on("master_command")
def h2(data):
    print(f"==> HIT master_command {data}", flush=True)
    received.append(("u", data))


@sio.on("change")
def h3(data):
    print(f"==> HIT change {data}", flush=True)


print(f"Connect to {URL}/ws/sync/...", flush=True)
sio.connect(
    URL,
    socketio_path="/ws/sync/",
    auth={"token": KEY},
    transports=["websocket"],
    wait=True,
    wait_timeout=15,
)
print(f"Connected. Waiting 30s for events...", flush=True)

# Aspetto con sleep e tengo viva la connessione
deadline = time.time() + 30
while time.time() < deadline:
    if not sio.connected:
        print(f"==> sio.connected = False!", flush=True)
        break
    time.sleep(1)

print(f"Final: received={len(received)} events", flush=True)
sio.disconnect()
