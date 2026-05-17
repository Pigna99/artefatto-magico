"""Piper TTS daemon persistente + pool per preset multipli.

Un daemon Piper carica il modello onnx una volta sola e tiene il processo
aperto, leggendo righe da stdin e scrivendo file WAV in una tmpdir.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from config import PIPER_PY, VOICES_DIR


class PiperDaemon:
    """Un Piper persistente per ciascun preset (voce + length-scale)."""

    _WROTE_RE = re.compile(r"Wrote\s+(\S+\.wav)")

    def __init__(self, voice: str, length_scale: str):
        self.voice = voice
        self.length_scale = length_scale
        self.tmpdir = Path(tempfile.mkdtemp(prefix="piper_"))
        self.proc = subprocess.Popen(
            [
                str(PIPER_PY), "-m", "piper",
                "-m", voice,
                "--data-dir", str(VOICES_DIR),
                "--length-scale", length_scale,
                "-d", str(self.tmpdir),
                "--output-dir-naming", "timestamp",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def synth(self, text: str) -> Path:
        self.proc.stdin.write(text.replace("\n", " ").strip() + "\n")
        self.proc.stdin.flush()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            line = self.proc.stderr.readline()
            if not line:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"piper rc={self.proc.returncode}")
                continue
            m = self._WROTE_RE.search(line)
            if m:
                wav = Path(m.group(1))
                if wav.exists() and wav.stat().st_size > 44:
                    return wav
                raise RuntimeError(f"piper: WAV vuoto: {wav}")
        raise RuntimeError("piper: timeout")

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class PiperPool:
    """Tiene fino a due daemon (locale e turbo) caldi."""

    def __init__(self):
        self._daemons: dict[str, PiperDaemon] = {}

    def get(self, preset: dict) -> PiperDaemon:
        key = preset["voice"] + "@" + preset["length_scale"]
        if key not in self._daemons:
            self._daemons[key] = PiperDaemon(preset["voice"], preset["length_scale"])
        return self._daemons[key]

    def close_all(self):
        for d in self._daemons.values():
            try:
                d.close()
            except Exception:
                pass
        self._daemons.clear()


def apply_sox(in_wav: Path, effects: list[str]) -> Path:
    out = in_wav.with_suffix(".fx.wav")
    subprocess.run(
        ["sox", str(in_wav), str(out), *effects],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=True,
    )
    return out


def play_wav(wav: Path) -> subprocess.Popen:
    return subprocess.Popen(["paplay", str(wav)])
