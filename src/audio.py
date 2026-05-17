"""Riproduzione audio + gestione stop forzato.

Mantiene una lista dei `paplay` in corso così l'azione "stop voce" può
terminarli tutti immediatamente.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from tts import play_wav
from config import log_event


class AudioPlayer:
    """Wrapper attorno a `paplay` con coda e stop forzato."""

    def __init__(self):
        self._procs: list[subprocess.Popen] = []
        self.stop_flag = False

    def play_blocking(self, wav: Path) -> float:
        """Riproduce un WAV bloccando finché paplay finisce o stop_flag scatta.
        Ritorna la durata effettiva in secondi."""
        t0 = time.perf_counter()
        proc = play_wav(wav)
        self._procs.append(proc)
        try:
            proc.wait()
        finally:
            if proc in self._procs:
                self._procs.remove(proc)
        return time.perf_counter() - t0

    def stop_all(self) -> int:
        """Termina tutti i processi paplay in corso. Ritorna quanti ne ha uccisi."""
        self.stop_flag = True
        killed = 0
        for proc in list(self._procs):
            if proc.poll() is None:
                try:
                    proc.terminate()
                    killed += 1
                except Exception:
                    pass
                try:
                    proc.wait(timeout=0.3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self._procs.clear()
        log_event("tts.stop", killed=killed)
        return killed

    def reset(self):
        """Riarma il player per una nuova frase (chiama all'inizio di speak)."""
        self.stop_flag = False
