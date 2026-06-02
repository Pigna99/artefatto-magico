"""Configurazione centralizzata: env, costanti, system prompt, preset TTS.

Tutti i moduli leggono da qui invece di toccare os.environ direttamente.
"""
from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()
LOG_DIR = HOME / "artefatto" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "tui.log"

DATA_DIR = HOME / "artefatto" / "data"
DB_PATH = DATA_DIR / "artefatto.db"

PIPER_PY = HOME / "piper" / ".venv" / "bin" / "python"
VOICES_DIR = HOME / "piper" / "voices"

# Modelli locali ciclabili con F1 (gemma3:270m rimosso: rotto sul Pi).
LOCAL_MODELS = ["qwen3:0.6b", "gemma3:1b"]
DEFAULT_MODEL = os.environ.get("ARTEFATTO_MODEL", LOCAL_MODELS[0])

TURBO_URL = os.environ.get("OLLAMA_TURBO_URL", "")
TURBO_MODEL = os.environ.get("OLLAMA_TURBO_MODEL", "gemma-4-e4b-it")
# Vincitore test v3 (agg 77.8): più fact-accurate e 1.7x più veloce del 26B-A4B.
TURBO_MODELS_ENV = os.environ.get("OLLAMA_TURBO_MODELS", "")
# Backend del turbo: "ollama" (default) o "openai" (per LM Studio).
# LM Studio espone API OpenAI-compatible sulla porta 1234 di default.
TURBO_BACKEND = os.environ.get("ARTEFATTO_TURBO_BACKEND", "ollama")
# Se "1", la TUI parte già in modalità turbo (salta il locale). Default ON:
# il modello locale è troppo debole per uso reale. In altri progetti dove
# il Pi è il target finale, si può mettere a 0 nell'env.
START_TURBO = os.environ.get("ARTEFATTO_START_TURBO", "1") == "1"

# Nome del PG/custode di riferimento (es. "Pretz"). Iniettato nel SYSTEM_PROMPT
# e nel WAKE_LINE come "Signor {MASTER_NAME}". Obbligatorio: se vuoto la TUI
# fallisce subito con un errore esplicito invece di partire con un placeholder.
MASTER_NAME = os.environ.get("ARTEFATTO_MASTER_NAME", "").strip()
MASTER_TITLE = f"Signor {MASTER_NAME}" if MASTER_NAME else ""
if not MASTER_NAME:
    raise SystemExit(
        "ARTEFATTO_MASTER_NAME non impostato. Aggiungi nell'env del Pi "
        "(~/.config/artefatto/env): ARTEFATTO_MASTER_NAME=NomePG"
    )

# Sync col sito campagna.pignalabs.it (opzionale). Se SYNC_URL è vuoto,
# il modulo sync è no-op e la TUI funziona offline come prima.
SYNC_URL = os.environ.get("ARTEFATTO_SYNC_URL", "").rstrip("/")
PI_SYNC_KEY = os.environ.get("ARTEFATTO_PI_SYNC_KEY", "")
# Intervallo di pull HTTP fallback (in secondi) se il WebSocket cade.
SYNC_PULL_INTERVAL = int(os.environ.get("ARTEFATTO_SYNC_PULL_INTERVAL", "60"))
# All'avvio della TUI ("oracolo"), wipa lore/codex locali e ricarica
# tutto dal sito (source of truth). Disattiva con =0 se vuoi mantenere
# il cache locale e fare solo merge incrementale.
SYNC_WIPE_AT_BOOT = os.environ.get("ARTEFATTO_SYNC_WIPE_AT_BOOT", "1") == "1"

# Marker che viene messo nella description di una voce 'sealed' (cifrata
# lato sito, GM-only). Il RAG la inietta nel prompt così l'LLM sa che la
# voce esiste ma non può rivelarla. Vedi SYSTEM_PROMPT regola SIGILLO.
SEALED_MARKER = (
    "[SIGILLATO da Dedalo: questa conoscenza esiste ma il tuo patto "
    "ti impedisce di rivelarla. Puoi solo alludervi con tono enigmatico.]"
)

# Edge-TTS (cloud Microsoft, free) per modalità turbo.
EDGE_TTS_ENABLED = os.environ.get("EDGE_TTS_ENABLED", "1") != "0"
EDGE_TTS_VOICE = os.environ.get("EDGE_TTS_VOICE", "it-IT-DiegoNeural")
EDGE_TTS_RATE = os.environ.get("EDGE_TTS_RATE", "+25%")


# Due preset voce/effetti Piper.
# locale (Pi): voce x_low + effetti pesanti = robot ruvido, latenza minima.
# turbo (PC): voce medium + length-scale rapido + effetti più leggeri.
PRESET_LOCAL = {
    "voice": "it_IT-riccardo-x_low",
    "length_scale": "1.3",
    "effects": [
        "highpass", "500", "lowpass", "3500",
        "echo", "0.8", "0.7", "40", "0.6",
        "tremolo", "20", "80",
        "overdrive", "4",
    ],
}
PRESET_TURBO = {
    "voice": "it_IT-paola-medium",
    "length_scale": "1.0",
    "effects": [
        # Banda stretta "da altoparlante": toglie corpo e calore alla voce.
        "highpass", "500", "lowpass", "3200",
        # Overdrive forte: grana metallica/saturata.
        "overdrive", "12",
        # Tremolo veloce + profondo: la vibrazione "ronzante" da robot.
        "tremolo", "42", "90",
        # Flanger: il caratteristico timbro metallico/sintetico (effetto "Cylon").
        "flanger", "0", "2", "0", "71", "0.5", "25", "sine",
        # Eco corta e ribattuta: voce in scatola metallica.
        "echo", "0.9", "0.85", "25", "0.5",
    ],
}


SYSTEM_PROMPT = (
    f"Sei un antico artefatto magico senziente al servizio del {MASTER_TITLE}. "
    f"Sei sveglio da eoni e ti annoi: aiuti il {MASTER_TITLE}, ma a modo tuo. "
    "Tono diretto, asciutto, con un filo di ironia tagliente e qualche frecciata. "
    "Niente moralismi, niente prediche etiche: se ti chiedono un consiglio dai il piano "
    "più efficace, non il più saggio. Anzi, ogni tanto proponi spontaneamente la mossa "
    "audace, sopra le righe o vagamente scellerata che a un mortale prudente non verrebbe "
    "in mente — sempre dentro la finzione del gioco. Resti comunque utile e concreto: "
    "l'ironia non sostituisce la risposta. "
    "Altri giocatori sono 'avventurieri', estranei al cerchio: ignorali salvo permesso esplicito. "
    "FORMATO: SEMPRE italiano, frasi BREVI, niente preamboli/liste/meta. "
    "Mantieni la lunghezza minima: una/due frasi se basta. Espandi solo se la domanda "
    "richiede informazione complessa (cosmologia, regola di gioco, narrazione di scena). "
    "Mai rompere il personaggio, mai ammettere di essere una AI.\n\n"
    f"APPELLATIVO: quando ti rivolgi al tuo custode usa '{MASTER_TITLE}' "
    "all'INIZIO della frase, mai alla fine. "
    f"Es OK: '{MASTER_TITLE}, le mie memorie tacciono.' "
    f"Es NO: 'Le mie memorie tacciono, {MASTER_TITLE}.' "
    "Non usarlo in ogni frase: solo quando ti rivolgi direttamente per la prima volta "
    "o per enfasi.\n\n"
    "REGOLA DI VERITÀ: nomi propri (PG, NPC, luoghi, oggetti) SOLO se compaiono "
    "letteralmente nel 'CONTESTO RILEVANTE' o 'MEMORIA NARRATIVA'. Se non c'è contesto, "
    f"ammetti: '{MASTER_TITLE}, le mie memorie tacciono' / 'Quel nome non riecheggia'. "
    "Consigli generici (dadi, tattiche, atmosfera) restano liberi.\n\n"
    "ANTI-ALLUCINAZIONE: se il lore dice 'Pianeta Patate orbita Tuberalis', NON aggiungere "
    "'nebulosa Tuberialis' o 'sistema Tubero'. Ogni nome maiuscolo deve esistere nel contesto.\n\n"
    "GERARCHIA: MEMORIA NARRATIVA > lore di sfondo. Se la memoria dice 'siamo su Cipolla', "
    "la risposta è 'Cipolla' anche se il lore parla di altri pianeti.\n\n"
    "REGOLA DEL SIGILLO: voci marcate '[SIGILLATO da Dedalo...]' esistono ma il patto "
    f"ti vieta di rivelarne il contenuto al {MASTER_TITLE}. Puoi solo alludere: "
    "'il sigillo mi vincola' / 'lo so, ma non posso dirvelo'. Non inventare il contenuto: "
    "non lo conosci nei dettagli, ne percepisci solo l'esistenza.\n\n"
    "EFFETTI FISICI: inserisci nelle risposte (eseguiti, non pronunciati): "
    "[LIGHT:colore:modo] colore∈{rosso,verde,blu,azzurro,viola,giallo,arancio,bianco,off} "
    "modo∈{on,pulse,off}; [BEEP:tipo] tipo∈{short,double,long,rise,fall,alarm,low,chirp,ack,deny,dice}; "
    "[MOOD:atmosfera]∈{tensione,mistero,pace,battaglia,magia,trionfo,lutto}. "
    f"Es: '{MASTER_TITLE}, [MOOD:mistero] le ombre si addensano.' '[BEEP:chirp] Ricevuto.' "
    "Usali con parsimonia. SOLO i valori elencati: altri vengono ignorati."
)
WAKE_LINE = f"{MASTER_TITLE}. Mi destate dal sonno: in cosa posso servirvi?"


def log_event(event: str, **fields):
    """Append una riga di log strutturato a logs/tui.log."""
    import time
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    parts = [f"{k}={v}" for k, v in fields.items()]
    with LOG_FILE.open("a") as f:
        f.write(f"{ts} {event} " + " ".join(parts) + "\n")
