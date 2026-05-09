"""Client TTS remoto basato su edge-tts (Microsoft Edge Read Aloud).

Espone la stessa interfaccia di PiperDaemon (`synth(text) -> Path`).

edge-tts e' una libreria Python che parla via WebSocket coi server di
Microsoft. Le voci italiane disponibili includono:
  it-IT-DiegoNeural    (maschile, autorevole)  ← default
  it-IT-ElsaNeural     (femminile chiara)
  it-IT-IsabellaNeural (femminile matura)
  it-IT-GianniNeural   (maschile giovane)

Il flusso e':
  testo -> edge-tts -> MP3 -> ffmpeg -> WAV PCM 22050 Hz mono
Cosi' poi sox puo' applicare gli effetti CYLON come per Piper.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

try:
    import edge_tts  # type: ignore
except Exception:  # noqa: BLE001
    edge_tts = None  # type: ignore


class EdgeTTSClient:
    """Sintesi via edge-tts (servizio cloud Microsoft)."""

    def __init__(self, voice: str = "it-IT-DiegoNeural", rate: str = "+50%",
                 pitch: str = "+0Hz"):
        self.voice = voice
        # rate: "+50%" velocizza del 50%, "-10%" rallenta. Va passato come
        # stringa con segno; edge-tts lo accetta direttamente.
        self.rate = rate
        self.pitch = pitch
        self.tmpdir = Path(tempfile.mkdtemp(prefix="edge_tts_"))

    def is_ready(self, timeout: float = 3.0) -> bool:
        if edge_tts is None:
            return False
        # Probe HTTP rapido al servizio Microsoft (no auth, no quota visibile).
        # Se la rete e' giu' restituiamo False senza far esplodere la sessione.
        try:
            import urllib.request
            urllib.request.urlopen("https://speech.platform.bing.com/", timeout=timeout)
            return True
        except Exception:
            try:
                # alcuni endpoint di edge-tts non rispondono a GET nudo, fallback DNS
                import socket
                socket.gethostbyname("speech.platform.bing.com")
                return True
            except Exception:
                return False

    def list_voices(self) -> list[str]:
        # Solo voci italiane (le altre non ci interessano per questo progetto)
        return [
            "it-IT-DiegoNeural",
            "it-IT-ElsaNeural",
            "it-IT-IsabellaNeural",
            "it-IT-GianniNeural",
        ]

    def synth(self, text: str) -> Path:
        """Manda il testo al servizio edge-tts, riceve MP3, lo converte in WAV."""
        if edge_tts is None:
            raise RuntimeError("edge-tts non installato")
        text = text.strip().replace("\r", " ").replace("\n", " ")
        if not text:
            raise ValueError("synth: testo vuoto")

        ts = int(time.time() * 1000)
        mp3 = self.tmpdir / f"art_{ts}.mp3"
        wav = self.tmpdir / f"art_{ts}.wav"

        async def _gen():
            communicate = edge_tts.Communicate(
                text, self.voice, rate=self.rate, pitch=self.pitch
            )
            await communicate.save(str(mp3))

        try:
            asyncio.run(_gen())
        except RuntimeError:
            # Se gia' siamo in un loop (es. Textual), creiamo un loop nuovo in un thread
            import threading
            error: list[Exception] = []
            def run():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_gen())
                    loop.close()
                except Exception as e:
                    error.append(e)
            t = threading.Thread(target=run)
            t.start()
            t.join(timeout=60)
            if error:
                raise error[0]

        if not mp3.exists() or mp3.stat().st_size < 100:
            raise RuntimeError(f"edge-tts: MP3 vuoto ({mp3})")

        # Convert MP3 -> WAV PCM con ffmpeg
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3), "-ar", "22050", "-ac", "1", str(wav)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=True,
        )
        mp3.unlink(missing_ok=True)
        if wav.stat().st_size < 44:
            raise RuntimeError(f"edge-tts: WAV vuoto ({wav})")
        return wav

    def close(self):
        try:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
        except Exception:
            pass


# Alias retro-compatibile col vecchio import nella TUI
AllTalkClient = EdgeTTSClient


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest():
    voice = os.environ.get("EDGE_TTS_VOICE", "it-IT-DiegoNeural")
    print(f"voce: {voice}")
    c = EdgeTTSClient(voice=voice)
    print("ready:", c.is_ready())
    if not c.is_ready():
        return
    t0 = time.perf_counter()
    wav = c.synth("In tempi remoti, prima ancora che la luna conoscesse il proprio nome.")
    dt = time.perf_counter() - t0
    print(f"WAV: {wav} ({wav.stat().st_size} bytes, {dt:.2f}s)")


if __name__ == "__main__":
    _selftest()
