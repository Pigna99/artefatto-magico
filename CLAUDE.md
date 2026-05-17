# Artefatto Magico — note per Claude

## Hardware sul Raspberry Pi 4

### LED RGB (kit Elegoo) — catodo comune
- Zampa lunga (catodo) → **pin 9 (GND)**
- Anodi via resistore 220Ω → GPIO:
  - R → GPIO 17 (pin 11)
  - G → GPIO 27 (pin 13)
  - B → GPIO 22 (pin 15)
- Env: `ARTEFATTO_LED_ANODE=0`, `ARTEFATTO_LED_INVERT=0`
- Backend usa 3 PWMLED diretti (non RGBLED), polarità esplicita in `set_rgb()`.

### LED turbo (LED verde singolo)
- Anodo (zampa lunga) → **GPIO 23 (pin 16)** via resistore 220Ω
- Catodo → GND
- Env: `ARTEFATTO_PIN_TURBO=23` (override se vuoi un altro pin)
- Acceso fisso quando la modalità turbo è attiva, spento in locale.

### Buzzer (kit Elegoo)
- **Passivo** (cilindretto aperto sopra), suona toni veri via PWM.
- `+` → GPIO 18 (pin 12)
- `-` → GND (qualsiasi: pin 6, 9, 14, 20, 25, 30, 34, 39)
- Env: `ARTEFATTO_BUZZ_TYPE=passive`

### Test hardware
```
cd ~/artefatto && .venv/bin/python src/gpio_fx.py test
```
Cicla 7 colori → pulse rosso → 7 pattern beep → stati idle/thinking/speaking.

## Modelli AI (post full-test 2026-05-17)

**Locale (sul Pi):** `LOCAL_MODELS = ["qwen3:0.6b", "gemma3:1b"]`
- Default: `qwen3:0.6b` (più veloce e accurato di gemma3:1b in pratica).
- `gemma3:270m` rimosso: produceva risposte vuote nei test.

**Turbo (sul PC RX 6800):** `OLLAMA_TURBO_MODEL=aya-expanse:8b`
- Vincitore del world-test v2: 28/30 a 2.3s (italiano nativo Cohere).
- `gemma4:latest` ottiene 30/30 ma è 3-4× più lento (7-8s/risposta) — usalo
  solo per scene dove serve massima fedeltà narrativa.
- `qwen3:8b`, `qwen2.5:14b`, `granite3.1-dense:8b` ~26/30, alternative.

## File di config locale sul Pi
`~/.config/artefatto/env` (NON in git):
```
ARTEFATTO_MODEL=gemma3:270m
OLLAMA_TURBO_URL=http://192.168.1.100:11434
OLLAMA_TURBO_MODEL=gemma4:latest
ARTEFATTO_BUZZ_TYPE=passive
ARTEFATTO_LED_ANODE=1
```

## Sync codice PC → Pi
SSH alias `artefatto` configurato in `~/.ssh/config`. Repo su Pi in `~/artefatto/`.
```
scp <file_locale> artefatto:~/artefatto/<percorso>
```

## Effetti LED + buzzer — quando e come

### Stati semantici (chiamati dalla TUI in `src/tui.py`)

| Trigger | Metodo chiamato | Colore LED | Modo | Periodo | Beep | Significato |
|---|---|---|---|---|---|---|
| Avvio TUI | `fx.boot()` | bianco→azzurro fade-in | on | — | `rise` | accensione |
| Chiusura TUI | `fx.shutdown()` | fade-out → off | on | — | `fall` | spegnimento |
| Stop TTS (F8/Esc/Ctrl+X) | `fx.idle(c)` | bianco | pulse | 3.0s | — | torno in attesa |
| F1 cambio modello | + `flash` viola | viola lampo 0.25s | — | — | `short` | feedback tasto |
| F2 toggle local/turbo | + `flash` | arancio o azzurro 0.3s | — | — | `double` | feedback tasto |
| F5 mute on/off | + `flash` | rosso/verde 0.3s | — | — | `low`/`ack` | feedback tasto |
| Inizio LLM | `fx.thinking()` | azzurro | pulse | 1.2s | — | sto pensando |
| Ogni 12 token streaming | `fx.flash(giallo\|viola)` | lampo random 0.08s | — | — | — | "sta scrivendo" |
| Inizio TTS | `fx.speaking()` | verde | on | — | — | sto parlando |
| Fine TTS | `fx.idle(c)` | bianco | pulse | 3.0s | — | tornato in attesa |
| Errore LLM | `fx.error()` | rosso | pulse | 0.5s | `deny` | qualcosa è fallito |
| Errore TTS | `fx.error()` | rosso | pulse | 0.5s | `deny` | TTS è crashato |
| `/roll d20` (crit 20) | `fx.flash("giallo",1s)` | giallo | — | — | `dice` | tiro critico |
| `/roll d20` (fumble 1) | `fx.flash("rosso",1s)` | rosso | — | — | `dice` | fumble |
| `/roll d20` (≥15) | `fx.flash("verde",0.8s)` | verde | — | — | `dice` | successo |
| `/roll d20` (8-14) | `fx.flash("arancio",0.5s)` | arancio | — | — | `dice` | medio |
| `/roll d20` (<8) | `fx.flash("rosso",0.5s)` | rosso | — | — | `dice` | fallimento |

L'indicazione di modalità turbo è data dal **LED verde dedicato** (GPIO 23), non dal LED RGB.

### Tag inline nelle risposte LLM (consumati in `tui.py:1032` da `consume_tags`)

Il modello può inserire questi marker nella risposta. Vengono **eseguiti e rimossi** prima del TTS (l'AI non li pronuncia).

| Tag | Effetto |
|---|---|
| `[LIGHT:colore:on]` | LED fisso di quel colore |
| `[LIGHT:colore:pulse]` | LED pulsante (period 0.8s) |
| `[LIGHT:colore:off]` | LED spento |
| `[BEEP:tipo]` | Suona il pattern di buzzer |
| `[MOOD:atmosfera]` | Stato persistente per scene narrative |

Atmosfere disponibili (`MOODS` in `gpio_fx.py:~280`):

| Atmosfera | Colore | Modo | Periodo |
|---|---|---|---|
| `tensione` | rosso | pulse | 1.8s |
| `mistero` | viola | pulse | 2.5s |
| `pace` | verde | on | — |
| `battaglia` | rosso | pulse | 0.4s |
| `magia` | azzurro | pulse | 1.0s |
| `trionfo` | giallo | on | — |
| `lutto` | blu | pulse | 4.0s |

Colori riconosciuti: `rosso/red, verde/green, blu/blue, azzurro, cyan, viola/purple, giallo/yellow, arancio/orange, bianco/white, off`.

### Pattern di beep (definiti in `gpio_fx.py:228`)

Ogni step è `(frequenza_Hz, durata_tono, pausa_dopo)`.

| Tipo | Sequenza | Carattere |
|---|---|---|
| `short` | 880Hz 0.08s | bip breve |
| `double` | 880Hz 0.06s · pausa 0.08s · 880Hz 0.06s | doppio click |
| `long` | 440Hz 0.45s | nota lunga |
| `rise` | 440 → 660 → 880Hz | scala ascendente (conferma) |
| `fall` | 880 → 660 → 440Hz | scala discendente (chiusura) |
| `alarm` | 1320Hz × 3 | allarme acuto |
| `low` | 220Hz 0.3s | nota grave |
| `chirp` | 1200 → 1500 → 1100Hz | trillo R2D2-style |
| `ack` | 660 → 880Hz | conferma breve |
| `deny` | 660 → 440Hz | rifiuto/errore |
| `dice` | 6 toni rapidi pseudo-random | rumore di dado |

### Ciclo di vita di un turno

```
[idle]      bianco pulse 3s (respiro lento)
   ↓ utente preme invio
[thinking]  azzurro pulse 1.2s (respiro veloce)         ← fx.thinking() @ tui.py:881
   ↓ LLM risponde (può contenere tag [LIGHT:..] [BEEP:..])
[tag exec]  consume_tags() esegue tag → LED + beep      ← @ tui.py:1032
[speaking]  verde fisso                                  ← fx.speaking() @ tui.py:1009
   ↓ TTS finito (o F8 per stop)
[idle]      azzurro pulse 3s                             ← fx.idle() @ tui.py:1022
```

### Aggiungere nuovi effetti

- Nuovo colore: aggiungi entry in `COLORS` (`gpio_fx.py:67`)
- Nuovo pattern beep: aggiungi entry in `GpioFx.BEEP_PATTERNS` (`gpio_fx.py:228`)
- Nuovo stato semantico: aggiungi metodo `def xxx(self): with self._lock: self._state = _State(...)` e chiamalo dalla TUI

## Modalità input (TAB)

Ciclo `LIBERA → CODEX → ROLL → LORE` con beep `chirp` e bordo input colorato.
Quando NON sei in `libera`, qualunque testo digitato viene prefissato col comando della modalità:

| Modalità | Bordo | Prefisso aggiunto | Esempio scrittura → eseguito |
|---|---|---|---|
| libera | verde | nessuno | `chi è Re Patatone?` → LLM |
| codex | giallo | `/codex add ` | `Sessione 4 testo...` → `/codex add Sessione 4 testo...` |
| roll | accent | `/roll ` | `d20` → `/roll d20` |
| lore | magenta | `/lore add ` | `npc Eldrin un fratello caduto` → `/lore add npc Eldrin un fratello caduto` |

Un input che inizia con `/` bypassa sempre la modalità (resta interpretato come comando esplicito). Definito in [src/tui.py](src/tui.py) via `INPUT_MODES`.

## Struttura del codice (post-refactor 2026-05-17)

```
src/
├── tui.py              [465 righe] App Textual: layout, lifecycle, keybindings,
│                                     orchestrazione _llm_phase + _speak_phase
├── config.py           [104]      env, costanti, PRESET_LOCAL/TURBO, SYSTEM_PROMPT,
│                                     log_event()
├── widgets.py          [165]      StatBar, StatusPanel, HistoryInput, ChatLog
├── llm.py              [78]       build_messages_with_rag, chat_kwargs, stream_chat
├── commands.py         [164]      handle_slash + _cmd_lore/_cmd_codex/_cmd_roll
├── audio.py            [60]       AudioPlayer (paplay queue + stop_all)
├── repl.py             [235]      vecchio entry point CLI (mantenuto come fallback)
│
├── tts/                            Pacchetto TTS
│   ├── __init__.py    [16]       re-export pubblico
│   ├── piper.py       [105]      PiperDaemon, PiperPool, apply_sox, play_wav
│   ├── remote.py      [153]      EdgeTTSClient (cloud Microsoft)
│   └── sanitize.py    [45]       sanitize_for_tts, split_sentences, SENTENCE_END
│
├── db/                             Pacchetto persistenza SQLite + FTS5
│   ├── __init__.py    [9]        Database, Lore, CodexEntry
│   ├── core.py        [44]       Database = composizione mixin
│   ├── schema.py      [112]      DDL idempotente
│   ├── models.py      [32]       dataclass Lore, CodexEntry
│   ├── sessions.py    [44]       SessionsMixin (sessioni + messaggi)
│   ├── lore.py        [80]       LoreMixin (CRUD + FTS5 + RAG inject)
│   ├── codex.py       [96]       CodexMixin (resoconti narrativi)
│   ├── gm.py          [46]       GmConfigMixin (eventi GM + config k/v)
│   └── _fts.py        [9]        helper FTS5 condivisi
│
└── gpio_fx/                        Pacchetto LED RGB + buzzer
    ├── __init__.py    [9]        re-export pubblico (GpioFx, consume_tags)
    ├── __main__.py    [39]       self-test: python -m gpio_fx test
    ├── config.py      [48]       pin, polarità, gain, palette COLORS
    ├── backend.py     [126]      _RealBackend (gpiozero) + _MockBackend
    ├── effects.py     [200]      GpioFx: stati, mood, signature, flash, beep
    └── tags.py        [37]       consume_tags + regex [LIGHT/BEEP/MOOD]
```

**Regole di dipendenza** (rispetta queste se aggiungi codice):
- `config.py` non importa nulla del progetto (è la radice).
- `tts/`, `db/`, `gpio_fx/` non si conoscono fra loro.
- `widgets.py` non importa logica di business (solo Textual).
- `llm.py`, `commands.py`, `audio.py` possono importare `config.py`, `db/`, `gpio_fx/`, `tts/`.
- `tui.py` è l'unico orchestratore: importa da tutti, ma nessuno importa da lui.

**Estensione tipica:**
- Nuovo comando slash → aggiungi `_cmd_xxx()` in `commands.py`.
- Nuovo effetto LED → aggiungi metodo a `gpio_fx/effects.py`.
- Nuovo backend TTS → aggiungi modulo in `tts/` con `synth(text) -> Path`.
- Nuova tabella DB → estendi `db/schema.py` + crea mixin in `db/`.

## Convenzioni progetto
- TTS locale: Piper daemon persistente (no reload per frase).
- TTS turbo: edge-tts cloud, voce `it-IT-DiegoNeural` a `+25%`.
- DB: SQLite + FTS5 in `~/artefatto/data/artefatto.db`.
- RAG: text-based (no embeddings), `Database.search_lore()` con FTS5 OR-of-words.
- Prompt di sistema include "REGOLA DI VERITÀ" anti-allucinazione.
- I tag `[LIGHT:colore:modo]` e `[BEEP:tipo]` nelle risposte LLM sono consumati prima del TTS.
