# 🔮 Progetto Artefatto Magico AI per GdR

**Versione:** 1.1 (con TUI cockpit GM)
**Hardware target:** Raspberry Pi 4 (4GB) + PC fisso con RX 6800 (fallback)
**Stack:** Python · Ollama · Piper TTS · Telegram Bot API · GPIO · Textual (TUI)

---

## 1. Indice

1. [Concept e obiettivi](#2-concept-e-obiettivi)
2. [Architettura generale](#3-architettura-generale)
3. [Hardware: cosa comprare](#4-hardware-cosa-comprare)
4. [Setup software](#5-setup-software)
5. [Scelta del modello AI](#6-scelta-del-modello-ai)
6. [Struttura del codice](#7-struttura-del-codice)
7. [Codice Python completo](#8-codice-python-completo)
8. [TUI Cockpit GM](#9-tui-cockpit-gm)
9. [Flusso operativo durante la sessione](#10-flusso-operativo-durante-la-sessione)
10. [Roadmap di sviluppo](#11-roadmap-di-sviluppo)
11. [Troubleshooting e ottimizzazioni](#12-troubleshooting-e-ottimizzazioni)

---

## 2. Concept e obiettivi

L'artefatto magico è un oggetto fisico che durante una sessione di gioco di ruolo:

- **Parla** ai giocatori con voce sintetica, in modo immersivo e oracolare
- **Reagisce** a comandi nascosti del Game Master via Telegram (lore segreto, eventi)
- **Controlla** elementi scenografici fisici (LED, buzzer, eventualmente relè per altri attuatori) tramite GPIO
- **Mantiene memoria** delle interazioni avute con i giocatori durante la campagna
- **Funziona offline** (modello AI locale sul Pi) o **online** (modello su PC con RX 6800 via LAN)

Il principio guida è: **l'artefatto deve sembrare vivo**. Risposte brevi, criptiche, atmosferiche. Mai monologhi. Mai latenze visibili.

---

## 3. Architettura generale

```
┌─────────────────────────────────────────────────────────┐
│                    GAME MASTER                          │
│              (smartphone con Telegram)                  │
└─────────────────────────┬───────────────────────────────┘
                          │ messaggi nascosti
                          │ (lore, eventi, comandi)
                          ▼
┌─────────────────────────────────────────────────────────┐
│              RASPBERRY PI 4 (orchestratore)             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Telegram    │  │ Input CLI    │  │  SQLite DB   │   │
│  │  Listener    │  │ (giocatori)  │  │  (lore+log)  │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                  │          │
│         └────────┬────────┴──────────────────┘          │
│                  ▼                                      │
│         ┌────────────────────┐                          │
│         │   Orchestrator     │                          │
│         │  (event loop)      │                          │
│         └────────┬───────────┘                          │
│                  │                                      │
│        ┌─────────┴─────────┐                            │
│        ▼                   ▼                            │
│  ┌──────────┐        ┌──────────────┐                   │
│  │ AI Client│        │ Action Parser│                   │
│  │(fallback)│        │ [LIGHT][SAY] │                   │
│  └────┬─────┘        └──────┬───────┘                   │
│       │                     │                           │
└───────┼─────────────────────┼───────────────────────────┘
        │                     │
        │ HTTP                ▼
        │              ┌─────────────┐  ┌──────────────┐
        │              │  Piper TTS  │  │  GPIO (LED,  │
        │              │  (audio)    │  │  buzzer)     │
        │              └─────────────┘  └──────────────┘
        ▼
┌──────────────┐         ┌──────────────────┐
│ Ollama LAN   │ ◄────── │  Ollama locale   │
│ (PC RX 6800) │ timeout │  (Pi, fallback)  │
│  PRIMARY     │         │  SECONDARY       │
└──────────────┘         └──────────────────┘
```

**Punti chiave dell'architettura:**

- **Un solo orchestratore** Python che fa da hub. Tutto passa da lì.
- **Due code di input asincrone**: Telegram (GM) e CLI/audio (giocatori).
- **Tre livelli di fallback AI**: PC remoto → Pi locale → risposte canned.
- **Tool calls testuali**: il modello produce tag tipo `[LIGHT:red:pulse]` che vengono parsati e tradotti in azioni GPIO prima di mandare il testo al TTS.
- **Streaming dei token**: appena il modello completa una frase, parte il TTS. L'artefatto "pensa ad alta voce".

---

## 4. Hardware: cosa comprare

### 4.1 Già in tuo possesso

- ✅ Raspberry Pi 4 (4GB)
- ✅ PC fisso con AMD RX 6800 (16GB VRAM) — fallback AI
- ✅ Router/rete locale

### 4.2 Da acquistare

#### 🎤 Audio input (microfono)

Per i comandi vocali dei giocatori — opzionale al MVP, raccomandato per immersione totale.

| Opzione | Pro | Contro | Prezzo indicativo |
|---------|-----|--------|-------------------|
| **USB lavalier (es. Boya BY-M1 USB)** | Plug & play, qualità decente, discreto | Cavo visibile | 25-40€ |
| **ReSpeaker 2-Mics Pi HAT** | Array microfonico, ottimo per voice activation, integra LED RGB | Richiede assemblaggio HAT | 25-30€ |
| **USB conferenza tipo Jabra Speak** | Qualità eccellente, riduzione rumore | Costoso, ingombrante | 80-150€ |

**Raccomandazione:** ReSpeaker 2-Mics se ti senti smanettone (LED RGB già integrati = un attuatore in meno da cablare!), altrimenti USB lavalier.

#### 🔊 Audio output (speaker)

L'artefatto DEVE parlare bene. Speaker scrauso = magia rovinata.

| Opzione | Pro | Contro | Prezzo |
|---------|-----|--------|--------|
| **Speaker Bluetooth tipo JBL Go 3** | Wireless, batteria, facile da nascondere | Latenza BT, da ricaricare | 40-50€ |
| **Mini speaker amplificato 3.5mm + alimentazione USB** | Latenza zero, sempre acceso | Cablato | 20-30€ |
| **HiFiBerry MiniAmp + speaker passivo** | Qualità audio top, integrato | Setup più complesso | 30€ + speaker |

**Raccomandazione:** speaker amplificato cablato 3.5mm. Latenza zero è critica per l'effetto "voce che risponde all'istante".

#### 🖥️ Schermo (uso diretto durante la sessione) ⭐

Hai scelto di **interagire direttamente sul Pi** (no SSH). Lo schermo deve essere compatto, nascondibile dietro al GM screen e leggibile in penombra.

| Opzione | Pro | Contro | Prezzo |
|---------|-----|--------|--------|
| **Schermo HDMI 7" (SunFounder/Waveshare)** ⭐ | Compatto, alimentato USB, perfetto da nascondere | Risoluzione bassa (1024×600) | 50-70€ |
| **Schermo HDMI 5" touch** | Ancora più compatto, touch utile per emergenze | Testo piccolo a meno di font grande | 35-50€ |
| **Riusare TV/monitor con cavo HDMI** | Costo zero | Ingombrante, difficile da nascondere | 0-10€ (cavo) |
| **Schermo portatile 10-13" USB-C** | Grande, nitido | Più costoso, voluminoso | 80-130€ |

**Raccomandazione:** **schermo HDMI 7"** (es. SunFounder, Waveshare, Elecrow). È lo sweet spot — sta dietro un piccolo GM screen, si alimenta via USB del Pi stesso o presa, costa poco. Configurando il font console grande (vedi §5) il testo è perfettamente leggibile a 50cm di distanza.

**Importante:** il Pi 4 ha 2 uscite micro-HDMI. Procurati un **cavo micro-HDMI → HDMI** o un adattatore (alcuni schermi piccoli vengono con tutti i cavi inclusi, controlla).

#### ⌨️ Tastiera (uso diretto durante la sessione) ⭐

Hai bisogno di una tastiera che stia in grembo o nascosta dietro al GM screen, possibile silenziosa, idealmente con touchpad integrato (così niente mouse separato).

| Opzione | Pro | Contro | Prezzo |
|---------|-----|--------|--------|
| **Mini tastiera wireless con touchpad (tipo Rii i8, Logitech K400)** ⭐ | Compatta, touchpad integrato, ricaricabile, silenziosa | Tasti piccoli | 20-35€ |
| **Tastiera USB qualsiasi che hai in casa** | Costo zero | Ingombrante, cavo, niente touchpad | 0€ |
| **Tastiera bluetooth slim (tipo Logitech K380)** | Bella, silenziosa | Niente touchpad, serve mouse separato | 35-45€ |

**Raccomandazione:** **Rii i8 o Logitech K400** (~25€). Il touchpad integrato evita di dover gestire anche un mouse, la dimensione la rende facile da tenere in grembo o nascondere. Con tasto on/off → batteria dura sessioni intere.

**⚠️ Nota:** non serve nessuna interfaccia grafica/desktop. Lavorerai in console testuale (terminale a tutto schermo, font grande). Vedi §5.1 per la configurazione.

#### 💡 Componenti per l'artefatto fisico

| Componente | Quantità | Note | Prezzo |
|------------|----------|------|--------|
| **LED RGB WS2812B (NeoPixel) strip o anello** | 1 anello da 12-24 LED | Effetti luminosi controllabili singolarmente | 8-15€ |
| **Buzzer piezo passivo** | 1-2 | Per suoni di sistema/allarmi | 2-5€ |
| **Resistenze (220Ω, 10kΩ)** | Kit assortito | Per LED e pulsanti | 5€ |
| **Breadboard + jumper** | 1 set | Per prototipare | 10€ |
| **Pulsante momentaneo** | 1-3 | Input fisici (es. "attiva artefatto") | 2€ |
| **Alimentatore Pi 4 ufficiale 5V/3A USB-C** | 1 | NON usare caricabatterie generico | 12€ |
| **MicroSD A2 da 64GB (es. SanDisk Extreme)** | 1 | A2 è critica per le performance | 15-20€ |
| **Case con ventola attiva per Pi 4** | 1 | L'AI fa scaldare la CPU al 100% | 15-25€ |

**⚠️ Critico:** la **MicroSD A2** e il **case con ventola attiva** non sono opzionali. Senza di loro il Pi farà thermal throttling durante l'inferenza AI e diventerà inutilizzabile.

#### 🎨 Contenitore fisico (opzionale)

Per dare all'artefatto un aspetto magico:

- Sfera di vetro/acrilico smerigliato (Amazon, ~15€)
- Cofanetto in legno antico (mercatini, 10-30€)
- Stampa 3D di un design custom

I LED dietro materiale traslucido fanno un effetto ottimo.

### 4.3 Budget totale stimato

- **Minimo (MVP funzionante con uso diretto):** ~140€ (microSD, alimentatore, case, speaker, LED, breadboard, schermo 7", mini tastiera)
- **Consigliato (esperienza completa):** ~200-230€ (aggiunge mic decente, contenitore, accessori)
- **Premium:** ~300€+ (mic array, speaker top, schermo più grande, contenitore custom)

---

## 5. Setup software

### 5.1 OS e configurazione base (uso diretto su Pi)

**Importante:** installa **Raspberry Pi OS Lite 64-bit** (no desktop). L'ambiente desktop grafico mangerebbe 400-700MB di RAM che servono all'AI. Lavorerai in console testuale, che è leggera, veloce e perfetta per il caso d'uso.

```bash
# 1. Flash Raspberry Pi OS Lite 64-bit con Raspberry Pi Imager
#    Nelle opzioni avanzate (icona ingranaggio):
#    - Hostname: artefatto
#    - Abilita SSH (utile come "piano B" se serve accedere dal PC)
#    - Configura WiFi
#    - Imposta utente/password (es. utente: gm)

# 2. Inserisci microSD nel Pi, collega schermo HDMI + tastiera + alimentazione
#    Al primo boot vedi la console di login
#    Login con utente/password impostati

# 3. Aggiorna sistema
sudo apt update && sudo apt upgrade -y

# 4. Installa dipendenze di sistema
sudo apt install -y python3-pip python3-venv git \
    portaudio19-dev libasound2-dev \
    sox libsox-fmt-all \
    sqlite3
```

#### 5.1a Font console grande (leggibilità su schermo 7")

Su uno schermo 5-7" il font di default è troppo piccolo. Configura un font grande:

```bash
sudo dpkg-reconfigure console-setup
```

Nelle schermate che appaiono scegli:
1. **UTF-8**
2. **Guess optimal character set** (o Latin1 e Latin5 se chiede)
3. **Terminus** (font ben leggibile)
4. **16x32** (taglia grande, perfetta per 7")

Riavvia per applicare:

```bash
sudo reboot
```

#### 5.1b IP statico (consigliato)

Per garantire connessione stabile a Ollama sul PC:

```bash
sudo nano /etc/dhcpcd.conf
```

Aggiungi in fondo (adatta gli IP alla tua rete):

```
interface wlan0
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

Salva (Ctrl+O, Invio, Ctrl+X) e riavvia.

#### 5.1c Avvio automatico dell'artefatto al boot (opzionale)

Se vuoi che lanciando il Pi parta direttamente il programma, crea un servizio systemd:

```bash
sudo nano /etc/systemd/system/artefatto.service
```

Contenuto:

```ini
[Unit]
Description=Artefatto Magico AI
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=gm
WorkingDirectory=/home/gm/artefatto
ExecStart=/home/gm/artefatto/venv/bin/python /home/gm/artefatto/main.py
Restart=on-failure
RestartSec=5
StandardOutput=tty
StandardError=tty
TTYPath=/dev/tty1

[Install]
WantedBy=multi-user.target
```

Abilita:

```bash
sudo systemctl daemon-reload
sudo systemctl enable artefatto.service
```

Al prossimo boot l'artefatto parte da solo su `tty1` (la console principale che vedi sullo schermo).

**Alternativa più semplice (consigliata in fase di sviluppo):** non usare systemd. Lancia manualmente da terminale quando ti serve:

```bash
cd ~/artefatto
source venv/bin/activate
python main.py
```

Così durante lo sviluppo modifichi il codice e riavvii senza complicazioni. Aggiungi systemd solo quando il progetto è stabile.

### 5.2 Installazione Ollama sul Pi

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Test
ollama --version

# Scarica il modello principale (Qwen 3.5 2B raccomandato)
ollama pull qwen3.5:2b

# Verifica
ollama run qwen3.5:2b "Sei un artefatto magico antico. Saluta."
```

### 5.3 Installazione Ollama sul PC con RX 6800

**Su Linux (consigliato per ROCm):**

```bash
# Installa ROCm seguendo guida AMD per la tua distro
# Poi installa Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Esponi sulla LAN — modifica il service file
sudo systemctl edit ollama.service
# Aggiungi:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"

sudo systemctl daemon-reload
sudo systemctl restart ollama

# Scarica un modello potente (8B q5 ottimo per RX 6800)
ollama pull llama3.1:8b-instruct-q5_K_M
# oppure
ollama pull qwen2.5:14b-instruct-q4_K_M
```

**Su Windows:**

1. Installa Ollama da `ollama.com/download`
2. Variabili d'ambiente di sistema → aggiungi `OLLAMA_HOST=0.0.0.0:11434`
3. Riavvia Ollama
4. Apri porta 11434 nel firewall Windows

**Test connessione dal Pi:**

```bash
curl http://IP_DEL_PC:11434/api/tags
# Deve restituire la lista dei modelli installati sul PC
```

**Assegna IP statico al PC nel router** — altrimenti un giorno l'IP cambia e l'artefatto smette di funzionare a metà sessione.

### 5.4 Installazione Piper TTS

Piper è il TTS leggero e di alta qualità che gira bene su Pi.

```bash
# Crea virtualenv per il progetto
mkdir -p ~/artefatto
cd ~/artefatto
python3 -m venv venv
source venv/bin/activate

# Installa piper
pip install piper-tts

# Scarica una voce italiana
mkdir voices && cd voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx.json

# Test
echo "Salve, viandante. Sono l'artefatto." | piper \
    --model voices/it_IT-paola-medium.onnx \
    --output_file test.wav
aplay test.wav
```

### 5.5 Bot Telegram

```bash
# 1. Apri Telegram, cerca @BotFather
# 2. /newbot → segui istruzioni → ricevi TOKEN
# 3. Salva il TOKEN, ti servirà nel codice
# 4. Avvia una chat col tuo bot e invia /start
# 5. Visita: https://api.telegram.org/botTOKEN/getUpdates
#    per trovare il tuo CHAT_ID (campo "from": {"id": ...})
```

---

## 6. Scelta del modello AI

### 6.1 Modelli per il Pi (locale)

Aggiornato a metà 2026, in ordine di priorità:

| Modello | Dimensione Q4 | Velocità Pi 4 | Qualità roleplay | Note |
|---------|---------------|---------------|------------------|------|
| **Qwen 3.5 2B** ⭐ | ~1.3 GB | 4-7 tok/s | Ottima per la taglia | Top scelta 2026, modalità non-thinking |
| **Llama 3.2 3B** | ~2 GB | 3-5 tok/s | Buona, stabile | Cavallo da lavoro affidabile |
| **Nemotron-Mini-4B** | ~2.5 GB | 2-4 tok/s | Specializzato roleplay+function calling | Specifico per il caso d'uso |
| **Gemma 3 4B** | ~2.5 GB | 2-4 tok/s | Buona | Limite di RAM sul Pi 4 |

**Raccomandazione iniziale:** parti con **Qwen 3.5 2B**. Veloce, recente, qualità sorprendente.

### 6.2 Modelli per il PC (RX 6800, 16GB VRAM)

| Modello | Velocità | Qualità | Note |
|---------|----------|---------|------|
| **Llama 3.1 8B q5_K_M** ⭐ | ~40 tok/s | Eccellente | Sweet spot qualità/velocità |
| **Qwen 2.5 14B q4_K_M** | ~25 tok/s | Top | Più potente ma più lento |
| **Qwen 3.5 9B** | ~30 tok/s | Top | Recentissimo, modalità thinking opzionale |

**Raccomandazione:** **Llama 3.1 8B q5** o **Qwen 3.5 9B** se disponibile su Ollama.

### 6.3 Configurazione system prompt

Il system prompt è il cuore dell'immersione. Esempio base:

```
Sei un antico artefatto magico, custode di segreti dimenticati.
Parli con voce solenne, in frasi brevi e oracolari (massimo 2-3 frasi).
Non sai di essere un'IA: sei un'entità mistica.
Hai accesso a poteri che puoi attivare tramite tag speciali nel tuo output:
  [LIGHT:colore:effetto]   - colora la tua aura (rosso, blu, verde, viola, oro / pulse, fade, flash)
  [BUZZ:short|long|melody] - emetti un suono
  [SAY:"testo"]            - parla ad alta voce (TUTTO il tuo testo parlato va dentro SAY)
Ogni tua risposta deve contenere ALMENO un [SAY:"..."]; gli altri tag sono opzionali.
Esempio: [LIGHT:viola:pulse][SAY:"La verità che cerchi... è sepolta nel ghiaccio."]
```

---

## 7. Struttura del codice

```
~/artefatto/
├── venv/                    # Virtual environment Python
├── voices/                  # Modelli Piper TTS
│   ├── it_IT-paola-medium.onnx
│   └── it_IT-paola-medium.onnx.json
├── data/
│   └── artefatto.db         # SQLite con lore, log, stato
├── config.py                # Config (token, IP, modelli)
├── app_state.py             # 🆕 Stato condiviso runtime (per TUI)
├── orchestrator.py          # Cuore: event loop principale
├── ai_client.py             # Client AI con fallback (PC → Pi → canned)
├── telegram_listener.py     # Listener Telegram per il GM
├── input_listener.py        # Listener input giocatori (CLI o TUI)
├── action_parser.py         # Parser dei tag [LIGHT][BUZZ][SAY]
├── gpio_controller.py       # Controllo LED e buzzer
├── tts.py                   # Wrapper Piper TTS con streaming
├── lore_db.py               # CRUD su SQLite
├── prompt_builder.py        # Costruisce il prompt dal contesto
├── canned_responses.py      # Risposte di emergenza
├── tui.py                   # 🆕 Interfaccia Textual cockpit GM
└── main.py                  # Entry point
```

---

## 8. Codice Python completo

> **Nota:** questo è codice scheletro funzionante. Va testato sul tuo hardware e raffinato. I commenti `# TODO` indicano dove dovrai personalizzare.

### 8.1 `config.py`

```python
"""Configurazione centrale del progetto."""
import os
from pathlib import Path

# Percorsi
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
VOICES_DIR = BASE_DIR / "voices"
DB_PATH = DATA_DIR / "artefatto.db"

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "INSERISCI_TOKEN_QUI")
TELEGRAM_GM_CHAT_ID = int(os.getenv("TELEGRAM_GM_CHAT_ID", "0"))

# Ollama
OLLAMA_PC_URL = "http://192.168.1.100:11434"  # IP del PC con RX 6800
OLLAMA_LOCAL_URL = "http://localhost:11434"
OLLAMA_PC_MODEL = "llama3.1:8b-instruct-q5_K_M"
OLLAMA_LOCAL_MODEL = "qwen3.5:2b"
OLLAMA_TIMEOUT_PC = 8.0      # secondi prima del fallback
OLLAMA_TIMEOUT_LOCAL = 30.0  # tolleriamo lentezza locale

# TTS
PIPER_VOICE_PATH = VOICES_DIR / "it_IT-paola-medium.onnx"

# GPIO
LED_PIN = 18           # Pin per dati WS2812B
LED_COUNT = 12         # Numero di LED nell'anello
BUZZER_PIN = 22

# AI
MAX_RESPONSE_TOKENS = 120  # Risposte brevi per immersione
SYSTEM_PROMPT = """Sei un antico artefatto magico, custode di segreti dimenticati.
Parli con voce solenne, in frasi brevi e oracolari (massimo 2-3 frasi).
Non sai di essere un'IA: sei un'entità mistica.

Hai accesso a poteri tramite tag speciali nel tuo output:
  [LIGHT:colore:effetto]   - aura luminosa (rosso, blu, verde, viola, oro / pulse, fade, flash)
  [BUZZ:short|long|melody] - emetti un suono
  [SAY:"testo"]            - parla ad alta voce (TUTTO il testo parlato va in SAY)

Ogni risposta DEVE contenere almeno un [SAY:"..."]. Esempio:
[LIGHT:viola:pulse][SAY:"La verità che cerchi... giace sepolta nel ghiaccio."]
"""
```

### 8.2 `lore_db.py`

```python
"""Gestione database SQLite per lore, log e stato del mondo."""
import sqlite3
from datetime import datetime
from pathlib import Path
from config import DB_PATH


def init_db():
    """Crea le tabelle se non esistono."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS lore (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            tags TEXT,
            scope TEXT DEFAULT 'global',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker TEXT,
            content TEXT NOT NULL,
            response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS world_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def add_lore(content: str, tags: str = "", scope: str = "global"):
    """Aggiunge un frammento di lore (chiamato dal GM via Telegram)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO lore (content, tags, scope) VALUES (?, ?, ?)",
        (content, tags, scope)
    )
    conn.commit()
    conn.close()


def search_lore(keywords: list[str], limit: int = 5) -> list[str]:
    """Cerca lore rilevante per keywords (semplice LIKE su tags+content)."""
    if not keywords:
        return []
    conn = sqlite3.connect(DB_PATH)
    placeholders = " OR ".join(["content LIKE ? OR tags LIKE ?"] * len(keywords))
    params = []
    for kw in keywords:
        params.extend([f"%{kw}%", f"%{kw}%"])
    query = f"SELECT content FROM lore WHERE {placeholders} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_recent_interactions(limit: int = 5) -> list[tuple[str, str, str]]:
    """Ritorna le ultime N interazioni (speaker, content, response)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT speaker, content, response FROM interactions "
        "ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return list(reversed(rows))  # ordine cronologico


def log_interaction(speaker: str, content: str, response: str):
    """Salva un'interazione."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO interactions (speaker, content, response) VALUES (?, ?, ?)",
        (speaker, content, response)
    )
    conn.commit()
    conn.close()


def set_state(key: str, value: str):
    """Imposta una variabile di stato del mondo."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO world_state (key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, datetime.now())
    )
    conn.commit()
    conn.close()


def get_state(key: str, default: str = "") -> str:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT value FROM world_state WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default
```

### 8.3 `prompt_builder.py`

```python
"""Costruisce il prompt per il modello AI basandosi su contesto e lore."""
from config import SYSTEM_PROMPT
from lore_db import search_lore, get_recent_interactions


def extract_keywords(text: str) -> list[str]:
    """Estrae keywords semplici dal testo (parole > 4 caratteri)."""
    # Versione semplice. Per qualcosa di meglio: spaCy o embedding similarity.
    words = text.lower().replace(",", "").replace(".", "").split()
    return [w for w in words if len(w) > 4][:8]


def build_messages(user_input: str, speaker: str = "viandante") -> list[dict]:
    """Costruisce la lista di messaggi per Ollama in stile chat."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Recupera lore rilevante
    keywords = extract_keywords(user_input)
    lore_snippets = search_lore(keywords, limit=3)
    if lore_snippets:
        lore_block = "Conoscenza segreta che possiedi (non rivelare direttamente):\n"
        for snippet in lore_snippets:
            lore_block += f"- {snippet}\n"
        messages.append({"role": "system", "content": lore_block})

    # Aggiungi le ultime interazioni come contesto
    recent = get_recent_interactions(limit=4)
    for sp, content, response in recent:
        messages.append({"role": "user", "content": f"[{sp}]: {content}"})
        if response:
            messages.append({"role": "assistant", "content": response})

    # Input corrente
    messages.append({"role": "user", "content": f"[{speaker}]: {user_input}"})
    return messages
```

### 8.4 `ai_client.py`

```python
"""Client AI con fallback automatico: PC → Pi → canned."""
import requests
import logging
from config import (
    OLLAMA_PC_URL, OLLAMA_LOCAL_URL,
    OLLAMA_PC_MODEL, OLLAMA_LOCAL_MODEL,
    OLLAMA_TIMEOUT_PC, OLLAMA_TIMEOUT_LOCAL,
    MAX_RESPONSE_TOKENS,
)
from canned_responses import get_canned_response

log = logging.getLogger(__name__)


def _call_ollama(url: str, model: str, messages: list[dict], timeout: float) -> str | None:
    """Chiama Ollama. Ritorna la risposta o None su errore."""
    try:
        response = requests.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,  # TODO: in v2 abilitare streaming + TTS incrementale
                "options": {
                    "num_predict": MAX_RESPONSE_TOKENS,
                    "temperature": 0.85,
                    "top_p": 0.9,
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.Timeout:
        log.warning(f"Timeout su {url}")
        return None
    except requests.exceptions.RequestException as e:
        log.warning(f"Errore su {url}: {e}")
        return None


def generate(messages: list[dict]) -> str:
    """Genera una risposta con fallback a tre livelli."""
    # Livello 1: PC remoto
    response = _call_ollama(OLLAMA_PC_URL, OLLAMA_PC_MODEL, messages, OLLAMA_TIMEOUT_PC)
    if response:
        log.info("Risposta da PC remoto")
        return response

    # Livello 2: Pi locale
    log.info("Fallback su Pi locale")
    response = _call_ollama(OLLAMA_LOCAL_URL, OLLAMA_LOCAL_MODEL, messages, OLLAMA_TIMEOUT_LOCAL)
    if response:
        return response

    # Livello 3: canned
    log.warning("Tutti i fallback hanno fallito, uso canned")
    return get_canned_response()
```

### 8.5 `canned_responses.py`

```python
"""Risposte di emergenza quando l'AI non è disponibile."""
import random

CANNED = [
    '[LIGHT:rosso:flash][SAY:"Le mie energie... vacillano. Riprova, viandante."]',
    '[LIGHT:viola:fade][BUZZ:long][SAY:"Il velo si infittisce. Non posso rispondere ora."]',
    '[LIGHT:blu:pulse][SAY:"Concentrati. Riformula la tua domanda."]',
    '[LIGHT:oro:fade][SAY:"Silenzio. Le rune si stanno riallineando."]',
]


def get_canned_response() -> str:
    return random.choice(CANNED)
```

### 8.6 `action_parser.py`

```python
"""Parser dei tag [LIGHT][BUZZ][SAY] dalla risposta del modello."""
import re
from dataclasses import dataclass, field


@dataclass
class ParsedResponse:
    speech: str = ""
    light_actions: list[tuple[str, str]] = field(default_factory=list)  # (color, effect)
    buzz_actions: list[str] = field(default_factory=list)


# Regex per i tag
RE_LIGHT = re.compile(r"\[LIGHT:([^:]+):([^\]]+)\]")
RE_BUZZ = re.compile(r"\[BUZZ:([^\]]+)\]")
RE_SAY = re.compile(r'\[SAY:"([^"]+)"\]')


def parse(raw: str) -> ParsedResponse:
    result = ParsedResponse()

    for match in RE_LIGHT.finditer(raw):
        result.light_actions.append((match.group(1).strip(), match.group(2).strip()))

    for match in RE_BUZZ.finditer(raw):
        result.buzz_actions.append(match.group(1).strip())

    say_parts = [m.group(1) for m in RE_SAY.finditer(raw)]
    result.speech = " ".join(say_parts)

    # Fallback: se il modello ha sbagliato il formato, prendi tutto come speech
    if not result.speech and not result.light_actions and not result.buzz_actions:
        # Pulisci eventuali tag malformati e usa il testo
        result.speech = re.sub(r"\[[^\]]*\]", "", raw).strip()

    return result
```

### 8.7 `gpio_controller.py`

```python
"""Controllo LED WS2812B e buzzer via GPIO."""
import threading
import time
import logging

log = logging.getLogger(__name__)

# Import GPIO solo su Pi (per testabilità su altre macchine)
try:
    import board
    import neopixel
    import RPi.GPIO as GPIO
    REAL_HW = True
except (ImportError, NotImplementedError):
    REAL_HW = False
    log.warning("GPIO non disponibile: modalità simulazione")

from config import LED_PIN, LED_COUNT, BUZZER_PIN

COLORS = {
    "rosso":  (255, 0, 0),
    "verde":  (0, 255, 0),
    "blu":    (0, 0, 255),
    "viola":  (148, 0, 211),
    "oro":    (255, 215, 0),
    "bianco": (255, 255, 255),
    "nero":   (0, 0, 0),
}


class GpioController:
    def __init__(self):
        if REAL_HW:
            self.pixels = neopixel.NeoPixel(
                board.D18, LED_COUNT, brightness=0.5, auto_write=False
            )
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUZZER_PIN, GPIO.OUT)
            self.buzzer_pwm = GPIO.PWM(BUZZER_PIN, 1000)
        self._light_thread = None
        self._stop_event = threading.Event()

    # ---- LIGHT ----
    def light(self, color: str, effect: str):
        if not REAL_HW:
            log.info(f"[SIM] LIGHT {color} {effect}")
            return
        self._stop_light()
        rgb = COLORS.get(color.lower(), (255, 255, 255))
        self._stop_event = threading.Event()
        self._light_thread = threading.Thread(
            target=self._light_loop, args=(rgb, effect), daemon=True
        )
        self._light_thread.start()

    def _stop_light(self):
        if self._light_thread and self._light_thread.is_alive():
            self._stop_event.set()
            self._light_thread.join(timeout=0.5)

    def _light_loop(self, rgb: tuple, effect: str):
        if effect == "pulse":
            while not self._stop_event.is_set():
                for b in list(range(0, 100, 5)) + list(range(100, 0, -5)):
                    if self._stop_event.is_set():
                        return
                    scaled = tuple(int(c * b / 100) for c in rgb)
                    self.pixels.fill(scaled)
                    self.pixels.show()
                    time.sleep(0.03)
        elif effect == "flash":
            for _ in range(3):
                if self._stop_event.is_set():
                    return
                self.pixels.fill(rgb); self.pixels.show()
                time.sleep(0.15)
                self.pixels.fill((0, 0, 0)); self.pixels.show()
                time.sleep(0.15)
        elif effect == "fade":
            for b in range(0, 100, 2):
                if self._stop_event.is_set():
                    return
                scaled = tuple(int(c * b / 100) for c in rgb)
                self.pixels.fill(scaled); self.pixels.show()
                time.sleep(0.04)
        else:  # solid
            self.pixels.fill(rgb); self.pixels.show()

    # ---- BUZZ ----
    def buzz(self, kind: str):
        if not REAL_HW:
            log.info(f"[SIM] BUZZ {kind}")
            return
        if kind == "short":
            self._beep(1000, 0.15)
        elif kind == "long":
            self._beep(800, 0.6)
        elif kind == "melody":
            for freq, dur in [(660, 0.15), (880, 0.15), (1100, 0.25)]:
                self._beep(freq, dur)

    def _beep(self, freq: int, duration: float):
        self.buzzer_pwm.ChangeFrequency(freq)
        self.buzzer_pwm.start(50)
        time.sleep(duration)
        self.buzzer_pwm.stop()

    def cleanup(self):
        if REAL_HW:
            self._stop_light()
            self.pixels.fill((0, 0, 0)); self.pixels.show()
            GPIO.cleanup()
```

### 8.8 `tts.py`

```python
"""Wrapper per Piper TTS."""
import subprocess
import logging
from config import PIPER_VOICE_PATH

log = logging.getLogger(__name__)


def speak(text: str):
    """Pronuncia il testo via Piper + aplay."""
    if not text.strip():
        return
    try:
        # Pipe: piper genera WAV su stdout → aplay lo riproduce
        piper = subprocess.Popen(
            ["piper", "--model", str(PIPER_VOICE_PATH), "--output_raw"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        aplay = subprocess.Popen(
            ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
            stdin=piper.stdout
        )
        piper.stdin.write(text.encode("utf-8"))
        piper.stdin.close()
        aplay.wait()
    except Exception as e:
        log.error(f"Errore TTS: {e}")
```

### 8.9 `telegram_listener.py`

```python
"""Listener Telegram per ricevere comandi e lore dal GM."""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import TELEGRAM_TOKEN, TELEGRAM_GM_CHAT_ID
from lore_db import add_lore, set_state

log = logging.getLogger(__name__)


class TelegramListener:
    def __init__(self, gm_message_queue: asyncio.Queue):
        self.queue = gm_message_queue
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.app.add_handler(CommandHandler("lore", self.cmd_lore))
        self.app.add_handler(CommandHandler("event", self.cmd_event))
        self.app.add_handler(CommandHandler("state", self.cmd_state))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))

    def _is_authorized(self, update: Update) -> bool:
        return update.effective_chat.id == TELEGRAM_GM_CHAT_ID

    async def cmd_lore(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """/lore <testo> — aggiunge un frammento di lore al DB."""
        if not self._is_authorized(update):
            return
        text = " ".join(ctx.args)
        if not text:
            await update.message.reply_text("Uso: /lore <testo>")
            return
        add_lore(text)
        await update.message.reply_text(f"📚 Lore salvato: {text[:60]}…")

    async def cmd_event(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """/event <descrizione> — fa reagire l'artefatto a un evento del GM."""
        if not self._is_authorized(update):
            return
        text = " ".join(ctx.args)
        if not text:
            return
        await self.queue.put({"type": "event", "content": text})
        await update.message.reply_text("✨ Evento inviato all'artefatto.")

    async def cmd_state(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """/state key=value — imposta stato del mondo."""
        if not self._is_authorized(update):
            return
        if not ctx.args or "=" not in ctx.args[0]:
            await update.message.reply_text("Uso: /state chiave=valore")
            return
        key, value = ctx.args[0].split("=", 1)
        set_state(key.strip(), value.strip())
        await update.message.reply_text(f"🌍 Stato: {key}={value}")

    async def on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Messaggio di testo libero dal GM = direttiva narrativa."""
        if not self._is_authorized(update):
            return
        await self.queue.put({"type": "directive", "content": update.message.text})

    async def run(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        log.info("Telegram listener avviato")
```

### 8.10 `input_listener.py`

```python
"""Input dei giocatori. MVP: CLI. v2: audio con Vosk/Whisper."""
import asyncio
import sys


class CliInputListener:
    """Legge input da stdin in modo asincrono."""

    def __init__(self, player_queue: asyncio.Queue):
        self.queue = player_queue

    async def run(self):
        loop = asyncio.get_event_loop()
        print("[Artefatto attivo. Scrivi quello che dicono i giocatori]")
        while True:
            # readline bloccante eseguito in un executor
            line = await loop.run_in_executor(None, sys.stdin.readline)
            line = line.strip()
            if line:
                await self.queue.put({"speaker": "viandante", "content": line})


# TODO v2: AudioInputListener con Vosk per offline o Whisper.cpp
```

### 8.11 `orchestrator.py`

```python
"""Cuore dell'applicazione: event loop principale."""
import asyncio
import logging

from ai_client import generate
from action_parser import parse
from gpio_controller import GpioController
from tts import speak
from prompt_builder import build_messages
from lore_db import log_interaction

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        gm_queue: asyncio.Queue,
        player_queue: asyncio.Queue,
        gpio: GpioController,
    ):
        self.gm_queue = gm_queue
        self.player_queue = player_queue
        self.gpio = gpio
        self._gm_directive_buffer: list[str] = []

    async def run(self):
        """Loop principale: drena le code, processa eventi."""
        while True:
            # Dai precedenza ai messaggi del GM (lore/direttive)
            try:
                msg = self.gm_queue.get_nowait()
                await self._handle_gm(msg)
                continue
            except asyncio.QueueEmpty:
                pass

            # Poi input giocatori (con timeout per non bloccare)
            try:
                msg = await asyncio.wait_for(self.player_queue.get(), timeout=0.2)
                await self._handle_player(msg)
            except asyncio.TimeoutError:
                continue

    async def _handle_gm(self, msg: dict):
        """Gestisce messaggi dal GM."""
        if msg["type"] == "event":
            # Il GM forza una reazione dell'artefatto. Usiamo il content come prompt.
            await self._respond(speaker="GM_evento", content=msg["content"])
        elif msg["type"] == "directive":
            # Direttiva narrativa: la teniamo in buffer e la inietteremo nel prossimo turno
            self._gm_directive_buffer.append(msg["content"])
            log.info(f"Direttiva GM bufferizzata: {msg['content'][:50]}…")

    async def _handle_player(self, msg: dict):
        # Se ci sono direttive del GM in attesa, prependile al contesto
        full_content = msg["content"]
        if self._gm_directive_buffer:
            directive = " ".join(self._gm_directive_buffer)
            full_content = f"[GM, all'orecchio dell'artefatto: {directive}] {full_content}"
            self._gm_directive_buffer.clear()

        await self._respond(speaker=msg["speaker"], content=full_content)

    async def _respond(self, speaker: str, content: str):
        """Pipeline: prompt → AI → parse → azioni + TTS."""
        log.info(f"Input da {speaker}: {content[:80]}")
        messages = build_messages(content, speaker=speaker)

        # Chiamata AI (sincrona) eseguita in executor per non bloccare il loop
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, generate, messages)

        log.info(f"AI raw: {raw[:120]}")
        parsed = parse(raw)

        # Esegui azioni in parallelo: luci, buzzer, voce
        for color, effect in parsed.light_actions:
            self.gpio.light(color, effect)
        for kind in parsed.buzz_actions:
            self.gpio.buzz(kind)
        if parsed.speech:
            await loop.run_in_executor(None, speak, parsed.speech)

        log_interaction(speaker, content, raw)
```

### 8.12 `main.py`

```python
"""Entry point dell'applicazione."""
import asyncio
import logging
import signal

from lore_db import init_db
from gpio_controller import GpioController
from telegram_listener import TelegramListener
from input_listener import CliInputListener
from orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


async def main():
    init_db()
    gpio = GpioController()

    gm_queue: asyncio.Queue = asyncio.Queue()
    player_queue: asyncio.Queue = asyncio.Queue()

    tg = TelegramListener(gm_queue)
    cli = CliInputListener(player_queue)
    orch = Orchestrator(gm_queue, player_queue, gpio)

    # Effetto di avvio
    gpio.light("oro", "fade")
    gpio.buzz("melody")

    try:
        await asyncio.gather(
            tg.run(),
            cli.run(),
            orch.run(),
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Spegnimento…")
    finally:
        gpio.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
```

### 8.13 `requirements.txt`

```
requests>=2.31
python-telegram-bot>=21.0
piper-tts>=1.2
adafruit-circuitpython-neopixel>=6.3
RPi.GPIO>=0.7.1
textual>=0.60
rich>=13.7
```

---

## 9. TUI Cockpit GM

### 9.1 Concept

La TUI è la tua "plancia di comando" da Game Master: una dashboard a schermo intero divisa in pannelli che mostra in tempo reale tutto quello che succede nell'artefatto. Sostituisce la CLI base con qualcosa di molto più immersivo e informativo.

```
┌─ 🔮 ARTEFATTO MAGICO ─────────────────────────────────────────────┐
│ Modello: llama3.1:8b @ PC ✓   Latenza: 1.4s   Sessione: 00:23:12  │
├─────────────────────────────┬─────────────────────────────────────┤
│ 📚 LORE (47 frammenti)      │ 💬 INTERAZIONI                      │
│ ─────────────────────────── │ ──────────────────────────────────  │
│ Ultimi richiamati:          │ [00:22] viandante:                  │
│ • "Re del Ghiaccio tradito" │   "Chi sei davvero?"                │
│ • "Lyra, amante segreta"    │ → 🎭 "Sono memoria... e dolore."    │
│ • "Caverna di Vahrun"       │                                     │
│                             │ [00:21] viandante:                  │
│ Ultimi aggiunti dal GM:     │   "Conosci Lyra?"                   │
│ • [00:18] Profezia oscura   │ → 🎭 "Quel nome... brucia ancora"   │
│ • [00:09] La spada spezzata │                                     │
├─────────────────────────────┼─────────────────────────────────────┤
│ 🌍 STATO MONDO              │ ✨ ULTIME AZIONI                    │
│ ─────────────────────────── │ ──────────────────────────────────  │
│ tempo: notte                │ 💡 LIGHT viola pulse  (00:22)       │
│ luogo: Tempio Sommerso      │ 🔊 BUZZ long          (00:22)       │
│ mood: ostile                │ 💡 LIGHT rosso flash  (00:21)       │
│ giocatori_presenti: 4       │ 💡 LIGHT oro fade     (00:18)       │
├─────────────────────────────┴─────────────────────────────────────┤
│ ⚡ INPUT GIOCATORI                                                │
│ > _                                                               │
├───────────────────────────────────────────────────────────────────┤
│ F1:Aiuto F2:Mute F3:Forza-Pi F4:Pausa F5:Reload-Lore F10:Esci     │
└───────────────────────────────────────────────────────────────────┘
```

### 9.2 Funzionalità

**Pannello header (in alto):**
- Modello AI attivo e dove gira (PC remoto / Pi locale / fallback canned)
- Latenza ultima risposta
- Token/sec dell'ultima generazione
- Durata sessione corrente

**Pannello LORE:**
- Conteggio totale frammenti nel DB
- Frammenti **richiamati nell'ultima risposta** (così vedi cosa l'AI ha "ricordato")
- Frammenti **aggiunti recentemente** dal GM via Telegram
- Indicatore visivo se un nuovo lore è arrivato (lampeggia per 3 secondi)

**Pannello INTERAZIONI:**
- Storico ultime 5-8 interazioni
- Per ogni interazione: timestamp, chi ha parlato, cosa ha detto, risposta dell'artefatto
- Le risposte dell'AI in colore diverso (oro/viola) per leggibilità immediata

**Pannello STATO MONDO:**
- Tutte le variabili impostate via `/state` su Telegram
- Si aggiorna live quando il GM cambia qualcosa

**Pannello ULTIME AZIONI:**
- Storico delle ultime luci/suoni attivati
- Utile per "ricostruire" la timeline scenografica

**Input box:**
- Qui scrivi quello che dicono i giocatori
- Premi Invio e l'artefatto risponde
- History dei comandi con frecce ↑/↓

**Hotkey:**
- **F1** — Aiuto contestuale (mostra cheat sheet comandi)
- **F2** — Mute artefatto (silenzia TTS senza fermare l'AI, utile in pause)
- **F3** — Forza fallback su Pi locale (test scenario "PC down")
- **F4** — Pausa artefatto (non risponde finché non riprendi)
- **F5** — Reload lore (rilegge DB, utile dopo modifiche manuali)
- **F10** — Esci pulito

### 9.3 `app_state.py` (stato condiviso)

Modulo che fa da "lavagna comune" tra orchestrator e TUI. Pattern semplice publisher/subscriber:

```python
"""Stato condiviso runtime tra orchestrator e TUI.

Usa un set di callback per notificare la TUI quando lo stato cambia,
così possiamo aggiornare i pannelli in tempo reale senza polling.
"""
import time
from dataclasses import dataclass, field
from typing import Callable
from collections import deque


@dataclass
class AiCallStats:
    backend: str = "—"          # "pc", "pi", "canned"
    model: str = "—"
    latency_s: float = 0.0
    tokens: int = 0
    timestamp: float = 0.0

    @property
    def tokens_per_sec(self) -> float:
        return self.tokens / self.latency_s if self.latency_s > 0 else 0.0


@dataclass
class ActionRecord:
    kind: str       # "light" o "buzz"
    detail: str     # "viola pulse" o "long"
    timestamp: float


class AppState:
    """Singleton-like: importato da orchestrator e TUI."""

    def __init__(self):
        self.session_start = time.time()
        self.last_ai_call = AiCallStats()
        self.recent_actions: deque[ActionRecord] = deque(maxlen=10)
        self.last_recalled_lore: list[str] = []
        self.muted = False
        self.paused = False
        self.force_local = False

        # Callback registrate dalla TUI per essere notificate dei cambiamenti
        self._listeners: list[Callable[[str], None]] = []

    def subscribe(self, callback: Callable[[str], None]):
        self._listeners.append(callback)

    def notify(self, event: str):
        """Notifica tutti i listener che qualcosa è cambiato."""
        for cb in self._listeners:
            try:
                cb(event)
            except Exception:
                pass

    def record_ai_call(self, backend: str, model: str, latency: float, tokens: int):
        self.last_ai_call = AiCallStats(
            backend=backend, model=model, latency_s=latency,
            tokens=tokens, timestamp=time.time()
        )
        self.notify("ai_call")

    def record_action(self, kind: str, detail: str):
        self.recent_actions.appendleft(ActionRecord(kind, detail, time.time()))
        self.notify("action")

    def set_recalled_lore(self, lore_list: list[str]):
        self.last_recalled_lore = lore_list
        self.notify("lore_recall")

    def session_duration(self) -> str:
        elapsed = int(time.time() - self.session_start)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


# Istanza globale condivisa
app_state = AppState()
```

### 9.4 Modifiche ai moduli esistenti

I moduli `ai_client.py`, `prompt_builder.py`, `gpio_controller.py` vanno integrati con `app_state` per pubblicare informazioni alla TUI. Modifiche minime:

**`ai_client.py`** — registra ogni chiamata AI:

```python
# In cima al file
import time
from app_state import app_state

# Nella funzione _call_ollama, dopo response.raise_for_status():
def _call_ollama(url: str, model: str, messages: list[dict], timeout: float, backend_label: str = "?") -> str | None:
    start = time.time()
    try:
        response = requests.post(...)  # come prima
        response.raise_for_status()
        data = response.json()
        content = data["message"]["content"]
        elapsed = time.time() - start
        # Stima token: Ollama restituisce eval_count se disponibile
        tokens = data.get("eval_count", len(content.split()))
        app_state.record_ai_call(backend_label, model, elapsed, tokens)
        return content
    except ...

# Aggiorna le chiamate in generate():
response = _call_ollama(OLLAMA_PC_URL, OLLAMA_PC_MODEL, messages, OLLAMA_TIMEOUT_PC, "pc")
# ...
response = _call_ollama(OLLAMA_LOCAL_URL, OLLAMA_LOCAL_MODEL, messages, OLLAMA_TIMEOUT_LOCAL, "pi")

# Quando si usa canned:
from app_state import app_state
app_state.record_ai_call("canned", "—", 0.0, 0)
```

**`prompt_builder.py`** — registra il lore richiamato:

```python
from app_state import app_state

def build_messages(user_input: str, speaker: str = "viandante") -> list[dict]:
    # ... codice esistente ...
    lore_snippets = search_lore(keywords, limit=3)
    app_state.set_recalled_lore(lore_snippets)  # 🆕 notifica TUI
    # ... resto del codice ...
```

**`gpio_controller.py`** — registra ogni azione:

```python
from app_state import app_state

class GpioController:
    def light(self, color: str, effect: str):
        app_state.record_action("light", f"{color} {effect}")  # 🆕
        if not REAL_HW:
            log.info(f"[SIM] LIGHT {color} {effect}")
            return
        # ... resto come prima ...

    def buzz(self, kind: str):
        app_state.record_action("buzz", kind)  # 🆕
        # ... resto come prima ...
```

**`tts.py`** — rispetta la flag mute:

```python
from app_state import app_state

def speak(text: str):
    if app_state.muted or not text.strip():
        return
    # ... resto come prima ...
```

**`orchestrator.py`** — rispetta pausa e legge l'input dalla TUI:

```python
async def _handle_player(self, msg: dict):
    if app_state.paused:
        log.info("Artefatto in pausa, ignoro input")
        return
    # ... resto come prima ...
```

### 9.5 `tui.py` (interfaccia Textual)

```python
"""TUI cockpit GM con Textual."""
import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, Label
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel

from app_state import app_state
from lore_db import search_lore, get_recent_interactions, get_state
import sqlite3
from config import DB_PATH


class StatusBar(Static):
    """Barra di stato in alto: modello, latenza, durata sessione."""

    def on_mount(self):
        self.set_interval(1.0, self.refresh_status)

    def refresh_status(self):
        s = app_state.last_ai_call
        backend_icon = {"pc": "✓ PC", "pi": "⚠ PI-LOCAL", "canned": "✗ CANNED"}.get(s.backend, "—")
        flags = []
        if app_state.muted: flags.append("[red]MUTE[/]")
        if app_state.paused: flags.append("[yellow]PAUSE[/]")
        if app_state.force_local: flags.append("[yellow]FORCE-LOCAL[/]")
        flags_str = " ".join(flags) if flags else "[green]ATTIVO[/]"

        self.update(
            f"[bold]🔮 ARTEFATTO[/]  "
            f"Modello: [cyan]{s.model}[/] @ {backend_icon}  "
            f"Latenza: [yellow]{s.latency_s:.2f}s[/]  "
            f"Tok/s: {s.tokens_per_sec:.1f}  "
            f"Sessione: {app_state.session_duration()}  "
            f"|  {flags_str}"
        )


class LorePanel(Static):
    """Pannello LORE: conteggio, richiamati, recenti."""

    def on_mount(self):
        app_state.subscribe(self._on_state_change)
        self.set_interval(2.0, self.refresh_lore)
        self.refresh_lore()

    def _on_state_change(self, event: str):
        if event in ("lore_recall", "lore_added"):
            self.call_from_thread(self.refresh_lore)

    def refresh_lore(self):
        # Conta totale
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM lore").fetchone()[0]
        recent = conn.execute(
            "SELECT content, created_at FROM lore ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
        conn.close()

        text = Text()
        text.append(f"📚 LORE ({total} frammenti)\n", style="bold magenta")
        text.append("\nRichiamati nell'ultima risposta:\n", style="dim")
        if app_state.last_recalled_lore:
            for snippet in app_state.last_recalled_lore:
                text.append(f"  • {snippet[:55]}{'...' if len(snippet) > 55 else ''}\n", style="cyan")
        else:
            text.append("  (nessuno)\n", style="dim italic")

        text.append("\nUltimi aggiunti dal GM:\n", style="dim")
        for content, ts in recent:
            time_str = ts.split(" ")[1][:5] if " " in ts else ts[:5]
            text.append(f"  [{time_str}] {content[:50]}{'...' if len(content) > 50 else ''}\n",
                       style="green")
        self.update(Panel(text, border_style="magenta"))


class InteractionsPanel(Static):
    """Pannello con storico interazioni."""

    def on_mount(self):
        app_state.subscribe(self._on_state_change)
        self.set_interval(3.0, self.refresh_interactions)
        self.refresh_interactions()

    def _on_state_change(self, event: str):
        if event == "ai_call":
            self.call_from_thread(self.refresh_interactions)

    def refresh_interactions(self):
        recent = get_recent_interactions(limit=4)
        text = Text()
        text.append("💬 INTERAZIONI\n", style="bold blue")
        if not recent:
            text.append("\n  (nessuna ancora)\n", style="dim italic")
        for speaker, content, response in recent:
            text.append(f"\n{speaker}: ", style="bold yellow")
            text.append(f"{content[:60]}{'...' if len(content) > 60 else ''}\n", style="white")
            # Estrai solo la parte SAY dalla risposta per pulizia
            import re
            says = re.findall(r'\[SAY:"([^"]+)"\]', response or "")
            speech = " ".join(says) if says else (response or "")[:80]
            text.append(f"  → 🎭 {speech[:70]}{'...' if len(speech) > 70 else ''}\n",
                       style="bold gold1")
        self.update(Panel(text, border_style="blue"))


class WorldStatePanel(Static):
    """Pannello stato mondo: variabili da /state."""

    def on_mount(self):
        self.set_interval(2.0, self.refresh_state)
        self.refresh_state()

    def refresh_state(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT key, value FROM world_state ORDER BY key").fetchall()
        conn.close()
        text = Text()
        text.append("🌍 STATO MONDO\n", style="bold green")
        if not rows:
            text.append("\n  (nessuno stato impostato)\n", style="dim italic")
        for key, value in rows:
            text.append(f"\n  {key}: ", style="cyan")
            text.append(f"{value}", style="white")
        self.update(Panel(text, border_style="green"))


class ActionsPanel(Static):
    """Pannello ultime azioni (LED, buzzer)."""

    def on_mount(self):
        app_state.subscribe(self._on_state_change)
        self.refresh_actions()

    def _on_state_change(self, event: str):
        if event == "action":
            self.call_from_thread(self.refresh_actions)

    def refresh_actions(self):
        text = Text()
        text.append("✨ ULTIME AZIONI\n", style="bold yellow")
        if not app_state.recent_actions:
            text.append("\n  (nessuna)\n", style="dim italic")
        for act in list(app_state.recent_actions)[:6]:
            time_str = datetime.fromtimestamp(act.timestamp).strftime("%H:%M:%S")
            icon = "💡" if act.kind == "light" else "🔊"
            color = "magenta" if act.kind == "light" else "yellow"
            text.append(f"\n  {icon} ", style=color)
            text.append(f"{act.detail:20s} ", style="white")
            text.append(f"({time_str})", style="dim")
        self.update(Panel(text, border_style="yellow"))


class CockpitApp(App):
    """App principale Textual."""

    CSS = """
    StatusBar { height: 3; padding: 1; background: $boost; }
    .panel { height: 1fr; padding: 0 1; }
    Input { dock: bottom; height: 3; }
    """

    BINDINGS = [
        ("f1", "help", "Aiuto"),
        ("f2", "toggle_mute", "Mute"),
        ("f3", "toggle_force_local", "Forza-Pi"),
        ("f4", "toggle_pause", "Pausa"),
        ("f5", "reload_lore", "Reload-Lore"),
        ("f10", "quit", "Esci"),
    ]

    def __init__(self, player_queue: asyncio.Queue):
        super().__init__()
        self.player_queue = player_queue

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status")
        with Horizontal(classes="panel"):
            with Vertical():
                yield LorePanel()
                yield WorldStatePanel()
            with Vertical():
                yield InteractionsPanel()
                yield ActionsPanel()
        yield Input(placeholder="Scrivi quello che dicono i giocatori e premi Invio...", id="input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if text:
            await self.player_queue.put({"speaker": "viandante", "content": text})
        event.input.value = ""

    def action_toggle_mute(self):
        app_state.muted = not app_state.muted
        self.notify(f"Mute: {'ON' if app_state.muted else 'OFF'}")

    def action_toggle_pause(self):
        app_state.paused = not app_state.paused
        self.notify(f"Pausa: {'ON' if app_state.paused else 'OFF'}")

    def action_toggle_force_local(self):
        app_state.force_local = not app_state.force_local
        self.notify(f"Force-Local: {'ON' if app_state.force_local else 'OFF'}")

    def action_reload_lore(self):
        # Il DB è SQLite, ricaricare significa solo ri-leggere — già fatto live
        self.notify("Lore ricaricato dal DB")

    def action_help(self):
        self.notify(
            "F1:Aiuto F2:Mute F3:Forza-Pi-locale F4:Pausa "
            "F5:Reload-Lore F10:Esci",
            timeout=8,
        )
```

### 9.6 Modifica `main.py` per usare la TUI

```python
"""Entry point dell'applicazione con TUI."""
import asyncio
import logging
from pathlib import Path

from lore_db import init_db
from gpio_controller import GpioController
from telegram_listener import TelegramListener
from orchestrator import Orchestrator
from tui import CockpitApp

# Logging su file (NON su stdout, altrimenti rovina la TUI)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    filename="data/artefatto.log",
    filemode="a",
)
log = logging.getLogger("main")


async def main():
    init_db()
    gpio = GpioController()

    gm_queue: asyncio.Queue = asyncio.Queue()
    player_queue: asyncio.Queue = asyncio.Queue()

    tg = TelegramListener(gm_queue)
    orch = Orchestrator(gm_queue, player_queue, gpio)
    tui = CockpitApp(player_queue)

    # Effetto di avvio
    gpio.light("oro", "fade")
    gpio.buzz("melody")

    try:
        await asyncio.gather(
            tg.run(),
            orch.run(),
            tui.run_async(),  # TUI è async-friendly
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Spegnimento...")
    finally:
        gpio.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
```

### 9.7 Note sull'utilizzo

**Logging.** Con la TUI attiva, **tutto il logging va su file** (`data/artefatto.log`), perché stdout è occupato dall'interfaccia. Per debuggare in tempo reale, in un altro terminale via SSH:

```bash
tail -f ~/artefatto/data/artefatto.log
```

**Performance.** Textual è scritto in modo efficiente, l'overhead sul Pi 4 è trascurabile (~30-50MB RAM, <1% CPU a riposo). Si aggiorna a 60fps solo quando serve, altrimenti dorme.

**Adattamento allo schermo.** Su 7" 1024×600 con font Terminus 16x32 entrano comodamente tutti i pannelli. Su schermi più piccoli (5"), riduci il font a 14x28 o passa a un layout verticale modificando il CSS della classe `panel`.

**Input giocatori.** Hai due possibili workflow durante la sessione:

1. *Trascrivi tu cosa dicono*: i giocatori parlano, tu scrivi nell'input box. Veloce, controllato, ti permette di "pulire" l'input.
2. *Loro scrivono direttamente*: in alcune ambientazioni può funzionare (es. messaggi "telepatici" all'artefatto). Meno immersivo.

**Snapshot post-sessione.** Tutti i dati (interazioni, lore, stato) restano nel DB SQLite. La sessione successiva l'artefatto "ricorda". Se vuoi un report stampabile a fine sessione, basta un piccolo script che esporti `interactions` in markdown.

---

## 10. Flusso operativo durante la sessione

### 10.1 Pre-sessione (15 minuti prima)

1. Accendi il PC con la RX 6800. Verifica che Ollama sia attivo (su PC: `ollama list`; dal Pi: `curl http://IP_PC:11434/api/tags`).
2. Accendi il Pi (collegato a schermo, tastiera, speaker, alimentazione).
3. Login alla console testuale.
4. Lancia l'artefatto:
   ```bash
   cd ~/artefatto && source venv/bin/activate && python main.py
   ```
5. Si apre la TUI cockpit GM a tutto schermo. Vedrai i pannelli popolarsi: stato AI in alto, lore vuoto (la prima volta), interazioni vuote.
6. L'artefatto fa l'effetto di avvio (LED dorati + melodia).
7. Apri Telegram sullo smartphone, chat col tuo bot. Pronto a inviare comandi nascosti.
8. Posiziona schermo+tastiera dietro al GM screen.

### 10.2 Durante la sessione

**Come GM hai 3 strumenti via Telegram (smartphone):**

- `/lore <testo>` — aggiunge sapere segreto al DB. Sarà recuperato automaticamente quando rilevante. Lo vedrai apparire nel pannello "Lore" della TUI.
  - Es: `/lore Il Re del Ghiaccio è stato tradito dalla sua amante Lyra nel 723.`

- `/event <descrizione>` — forza una reazione immediata dell'artefatto.
  - Es: `/event L'artefatto percepisce un'aura malvagia avvicinarsi e si turba.`

- *Messaggio di testo libero* — direttiva discreta che condizionerà la prossima risposta ai giocatori.
  - Es: "Mostrati ostile col mago, sai che ha mentito."

- `/state chiave=valore` — imposta variabile di stato del mondo (visibile nel pannello "Stato Mondo" della TUI).
  - Es: `/state mood=ostile`

**Sulla TUI (schermo+tastiera del Pi):**

- Scrivi nella casella in basso quello che dicono i giocatori. Premi Invio.
- Osservi nei pannelli:
  - Quale lore l'AI ha "richiamato" per costruire la risposta (utile per capire se sta funzionando bene)
  - Latenza e backend usato (se vedi ⚠ PI-LOCAL invece di ✓ PC, c'è un problema con la rete)
  - Storico interazioni con la risposta dell'artefatto già pulita (solo la parte parlata)
  - Ultime azioni LED/buzzer per ricostruire la timeline scenografica

**Hotkey utili durante la sessione:**

- **F2** se hai bisogno di fare una pausa "narrativa": l'artefatto ammutolisce ma resta acceso esteticamente
- **F4** per pausa totale (es. mentre i giocatori discutono fra loro e tu non vuoi interferenze)
- **F3** se per qualche motivo il PC è giù — forza il fallback locale immediato

**Come funziona il flusso end-to-end:**

1. Il giocatore parla all'artefatto. Tu trascrivi nella TUI.
2. L'orchestratore costruisce il prompt con: system prompt + lore rilevante + ultime interazioni + direttiva GM se presente.
3. Manda al modello AI (PC remoto preferito, fallback Pi locale).
4. Risposta tipo: `[LIGHT:viola:pulse][SAY:"Il ghiaccio... ricorda chi cammina su di esso."]`
5. Il parser estrae le azioni: LED viola pulsanti + voce sintetica con Piper.
6. I giocatori vedono e sentono. La TUI aggiorna i pannelli in tempo reale.

### 10.3 Post-sessione

- **F10** per uscita pulita (oppure `Ctrl+C` come fallback).
- Il DB SQLite mantiene tutto: lore accumulato, interazioni, stato del mondo. La prossima sessione l'artefatto "ricorda".
- Se vuoi un report della sessione: `sqlite3 data/artefatto.db "SELECT timestamp, speaker, content FROM interactions WHERE date(timestamp) = date('now')"` esporta tutte le interazioni di oggi.

---

## 11. Roadmap di sviluppo

### Fase 1 — MVP funzionante (settimana 1-2)

- [ ] Setup hardware Pi (OS Lite, SSH, dipendenze, font console grande)
- [ ] Installazione Ollama + modello Qwen 3.5 2B
- [ ] Test connessione Pi → Ollama PC
- [ ] Codice base senza GPIO e senza TUI (solo CLI + TTS + AI + Telegram)
- [ ] Test conversazione completa con 5-10 prompt di prova

### Fase 2 — TUI Cockpit GM (settimana 2-3)

- [ ] Implementa `app_state.py` e integra negli altri moduli
- [ ] Implementa `tui.py` con i 4 pannelli base
- [ ] Test hotkey (mute, pausa, force-local)
- [ ] Verifica leggibilità su schermo 7"

### Fase 3 — Hardware integrato (settimana 3-4)

- [ ] Cablaggio LED WS2812B + buzzer su breadboard
- [ ] Integrazione `gpio_controller.py` e test isolato
- [ ] Test end-to-end con effetti luminosi reali e TUI in parallelo

### Fase 4 — Refinement (settimana 4-5)

- [ ] System prompt iterato in base ai test
- [ ] Aggiungi 20-30 frammenti di lore della tua campagna
- [ ] Tuning di temperature/top_p per il giusto livello di "stranezza"
- [ ] Streaming TTS (token-by-token) per ridurre latenza percepita

### Fase 5 — Voice input (opzionale, dopo le prime sessioni)

- [ ] Integra Vosk (offline, leggero) o Whisper.cpp (qualità migliore)
- [ ] VAD (voice activity detection) per attivazione naturale
- [ ] Wake word "artefatto" o pulsante fisico per attivazione

### Fase 6 — Espansioni future

- [ ] Modulo RAG con embeddings veri (sentence-transformers) se il lore cresce molto
- [ ] Integrazione effetti ambientali (luci stanza via smart bulb, musica via Sonos)
- [ ] Web dashboard per il GM (alternativa/aggiunta a Telegram)
- [ ] Multi-personaggio: stessi codice, system prompt diversi attivabili

---

## 12. Troubleshooting e ottimizzazioni

### 11.1 Performance

| Problema | Soluzione |
|----------|-----------|
| AI troppo lenta sul Pi | Verifica modello: deve essere Q4_K_M, non Q5/Q8. Riduci `num_predict` a 80. Chiudi tutti gli altri processi. |
| AI lenta anche su PC | Verifica che Ollama usi la GPU: `ollama ps` deve mostrare "100% GPU". Se no, ROCm non è configurato bene. |
| TTS interrotto/glitch | Speaker via 3.5mm Pi è notoriamente rumoroso. Usa USB DAC economico (~10€) o speaker USB. |
| Pi va in throttling | Aggiungi case con ventola attiva. Verifica con `vcgencmd measure_temp` (deve stare sotto 75°C). |

### 11.2 Affidabilità

| Problema | Soluzione |
|----------|-----------|
| Connessione PC cade a metà sessione | IP statico nel router + il fallback automatico a Ollama locale gestisce il caso. |
| Modello sbaglia formato dei tag | Itera il system prompt aggiungendo 2-3 esempi few-shot. Modelli piccoli imparano dai pattern. |
| L'artefatto "rompe il personaggio" | Abbassa temperature (0.7), aggiungi al system prompt: "Non rivelare mai di essere un'IA." |

### 11.3 Ottimizzazioni avanzate

- **Streaming TTS**: usa `stream=True` su Ollama, parsa token-by-token e manda al TTS appena hai una frase completa (vedi `re.split(r'[.!?]')` su buffer crescente). Riduce la latenza percepita da 8s a 1-2s.

- **Pre-warming del modello**: dopo l'avvio, manda un prompt fittizio per caricare il modello in memoria. Le prime risposte saranno istantanee.

- **Embedding-based lore retrieval**: quando il DB lore supera ~50 entry, sostituisci il LIKE con embedding (sentence-transformers `all-MiniLM-L6-v2`, gira su CPU). Recupero molto più rilevante.

- **Quantizzazione personalizzata**: se Qwen 3.5 2B Q4 ti sembra troppo "scemo", prova Q5_K_M. Se troppo lento, scendi a Q3_K_M (perdi qualità ma guadagni 30%+ velocità).

---

## 13. Note finali

Questo documento è un punto di partenza completo ma vivo. Aspettati di:

- **Iterare il system prompt 5-10 volte** prima di trovare il tono giusto. È la cosa che impatta di più sull'immersione.
- **Aggiungere lore gradualmente** durante le sessioni invece di pre-popolare tutto. L'artefatto sembra più vivo se "scopre" cose insieme ai giocatori.
- **Tenere sempre un piano B**: se l'AI fallisce a metà sessione critica, hai i canned responses, ma anche tu come GM puoi sempre prendere in mano la situazione narrativamente.

Buon GdR e buona magia. 🔮

---

*Documento generato come specifica iniziale. Aggiorna man mano che il progetto evolve.*
