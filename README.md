# Artefatto Magico

Un artefatto magico parlante per sessioni di gioco di ruolo, costruito su Raspberry Pi 4. L'oggetto fisico ascolta richieste, interroga un modello AI locale (o remoto su PC con GPU), e risponde con voce sintetica robotica processata in tempo reale.

Il principio guida: *l'artefatto deve sembrare vivo*. Risposte brevi, atmosferiche, mai monologhi.

## Stack

- **Hardware**: Raspberry Pi 4 (4GB), uscita audio 3.5mm, futuro mic via USB/HAT
- **OS**: Raspberry Pi OS Lite 64-bit (Debian 13 Trixie)
- **AI**: [Ollama](https://ollama.com) con `gemma3:1b` come fallback locale, modello più grande sul PC con RX 6800 come PRIMARY via LAN
- **TTS**: [Piper](https://github.com/rhasspy/piper) (voce `it_IT-riccardo-x_low`) + [SoX](http://sox.sourceforge.net/) per gli effetti robotici
- **Linguaggio**: Python 3.13

## Stato attuale

- ✅ TUI cockpit (Textual) con chat, sidebar di stato (CPU/RAM/temperatura colorate),
  selettore modello (F1) e switch locale ↔ turbo (F2), mute TTS (F5)
- ✅ REPL semplice come fallback (`ARTEFATTO_PLAIN=1 oracolo`)
- ✅ Pipeline TTS persistente (Piper daemon, evita ricaricamento onnxruntime ogni frase)
- ✅ Logging delle latenze in `logs/tui.log` / `logs/repl.log`
- 🔜 Bot Telegram per i comandi nascosti del Game Master
- 🔜 GPIO per LED/buzzer reattivi
- 🔜 Microfono + STT per input vocale dei giocatori

## Setup sul Raspberry Pi

```bash
# Sistema base
sudo apt install -y git python3-venv python3-pip build-essential \
    sox alsa-utils pulseaudio pulseaudio-module-bluetooth \
    bluetooth bluez

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:1b

# Repo del progetto
git clone https://github.com/Pigna99/artefatto-magico.git ~/artefatto
cd ~/artefatto
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Piper (in venv separato perché tira giù onnxruntime)
mkdir -p ~/piper/voices
python3 -m venv ~/piper/.venv
~/piper/.venv/bin/pip install piper-tts
~/piper/.venv/bin/python -m piper.download_voices it_IT-riccardo-x_low \
    --data-dir ~/piper/voices

# Alias comodo
echo "alias oracolo='~/artefatto/bin/artefatto'" >> ~/.bashrc
```

## Uso

```bash
oracolo
```

Apre la REPL: scrivi una domanda, l'artefatto risponde a schermo e ad alta voce. `Ctrl+C` per uscire.

Per usare un modello diverso al volo:

```bash
ARTEFATTO_MODEL=gemma3:270m oracolo
```

## Layout

```
artefatto-magico/
├── src/
│   ├── tui.py           # TUI cockpit (Textual): chat + status panel + keybindings
│   └── repl.py          # REPL semplice (fallback)
├── bin/
│   ├── artefatto        # launcher: TUI di default, REPL se ARTEFATTO_PLAIN=1
│   └── say              # script standalone: sintetizza una frase con preset CYLON
├── requirements.txt
├── .env.example
└── README.md
```

## Keybindings TUI

| Tasto | Azione |
|---|---|
| `F1` | Cicla modello locale (gemma3:270m → qwen3:0.6b → gemma3:1b) |
| `F2` | Switch locale ↔ turbo (PC con GPU, se configurato) |
| `F5` | Mute / unmute TTS |
| `Ctrl+C` | Esci |

## Preset audio

Il preset di default ("CYLON") è una catena SoX:
`highpass 500 → lowpass 3500 → echo metallico → tremolo 20Hz → overdrive`

Sopra una voce italiana maschile rallentata (`length-scale 1.3`). Risultato: voce robotica anni '70-'80, cibernetica, leggermente inquietante.
