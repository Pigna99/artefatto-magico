"""Client TTS remoto (AllTalk TTS / XTTS-v2 sul PC con GPU).

Espone la stessa interfaccia di PiperDaemon (`synth(text) -> Path`) così la
TUI lo può sostituire al daemon Piper quando in modalità turbo.

Le voci disponibili sono recuperate via /api/voices. La voce di default per
l'italiano è quella che il modello ha imparato; per voice cloning è
sufficiente mettere un file `<nome>.wav` nella cartella `voices/` di AllTalk.
"""
from __future__ import annotations

import os
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

import json


class AllTalkClient:
    """Client minimale per AllTalk TTS v2."""

    def __init__(self, base_url: str, voice: str, language: str = "it"):
        self.base = base_url.rstrip("/")
        self.voice = voice
        self.language = language
        self.tmpdir = Path(tempfile.mkdtemp(prefix="alltalk_"))

    # ------------------------------------------------------------------
    # Health & voices
    # ------------------------------------------------------------------

    def is_ready(self, timeout: float = 3.0) -> bool:
        try:
            req = urllib.request.Request(f"{self.base}/api/ready", method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="ignore").strip().lower()
            return "ready" in body
        except Exception:
            return False

    def list_voices(self, timeout: float = 5.0) -> list[str]:
        try:
            with urllib.request.urlopen(f"{self.base}/api/voices", timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            voices = data.get("voices", [])
            return [v.replace(".wav", "") if isinstance(v, str) else str(v) for v in voices]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synth(self, text: str) -> Path:
        """Manda testo al server, scarica il WAV finale, ritorna Path locale."""
        text = text.strip().replace("\r", " ").replace("\n", " ")
        if not text:
            raise ValueError("synth: testo vuoto")

        voice = self.voice if self.voice.endswith(".wav") else f"{self.voice}.wav"
        form = {
            "text_input": text,
            "text_filtering": "standard",
            "character_voice_gen": voice,
            "narrator_enabled": "false",
            "narrator_voice_gen": voice,
            "text_not_inside": "character",
            "language": self.language,
            "output_file_name": "artefatto",
            "output_file_timestamp": "true",
            "autoplay": "false",
            "autoplay_volume": "0.8",
            "streaming": "false",
        }
        data = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}/api/tts-generate",
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        # Timeout largo: la prima generazione carica il modello (~30s),
        # le successive tipicamente <3s.
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read().decode("utf-8"))

        # AllTalk risponde con: {"status":"generate-success",
        #                        "output_file_path": "...", "output_file_url":"/audio/x.wav"}
        url_path = payload.get("output_file_url") or ""
        if not url_path:
            raise RuntimeError(f"alltalk: payload inatteso: {payload}")

        wav_url = self.base + url_path if url_path.startswith("/") else url_path
        out_path = self.tmpdir / f"art_{int(time.time()*1000)}.wav"
        with urllib.request.urlopen(wav_url, timeout=60) as r, out_path.open("wb") as f:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        if out_path.stat().st_size < 44:
            raise RuntimeError(f"alltalk: WAV vuoto: {out_path}")
        return out_path

    def close(self):
        try:
            for p in self.tmpdir.glob("*"):
                p.unlink(missing_ok=True)
            self.tmpdir.rmdir()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest():
    base = os.environ.get("ALLTALK_URL", "http://192.168.1.100:7851")
    voice = os.environ.get("ALLTALK_VOICE", "female_01")
    print(f"AllTalk base: {base}, voice: {voice}")
    c = AllTalkClient(base, voice)
    print("ready:", c.is_ready())
    voices = c.list_voices()
    print(f"voices ({len(voices)}):", ", ".join(voices[:10]),
          "..." if len(voices) > 10 else "")
    if not c.is_ready():
        print("server non raggiungibile, esco")
        return
    print("synth in corso...")
    t0 = time.perf_counter()
    wav = c.synth("In tempi remoti, prima ancora che la luna conoscesse il proprio nome, io già vegliavo.")
    dt = time.perf_counter() - t0
    print(f"WAV: {wav}  ({wav.stat().st_size} bytes, {dt:.2f}s)")


if __name__ == "__main__":
    _selftest()
