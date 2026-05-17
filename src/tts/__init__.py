"""TTS backends + audio sanitization."""
from .piper import PiperDaemon, PiperPool, apply_sox, play_wav
from .sanitize import sanitize_for_tts, split_sentences, SENTENCE_END

try:
    from .remote import EdgeTTSClient
    AllTalkClient = EdgeTTSClient  # alias retrocompat
except Exception:
    EdgeTTSClient = None  # type: ignore
    AllTalkClient = None  # type: ignore

__all__ = [
    "PiperDaemon", "PiperPool", "apply_sox", "play_wav",
    "sanitize_for_tts", "split_sentences", "SENTENCE_END",
    "EdgeTTSClient", "AllTalkClient",
]
