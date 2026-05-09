# Benchmark modelli Ollama su Raspberry Pi 4 (4GB)

**Data:** 2026-05-09
**Hardware:** Raspberry Pi 4 Model B Rev 1.1, 4GB RAM, Debian 13 Trixie aarch64
**Ollama:** v0.23.2
**Prompt:** *"Sei un antico artefatto magico. Rispondi in una sola frase criptica in italiano. Domanda: chi sei?"*

## Risultati

| Modello | Size | eval rate (tok/s) | prompt eval (tok/s) | Risposta | Giudizio |
|---|---:|---:|---:|---|---|
| `gemma3:270m` | 290 MB | **11.48** | 91.84 | "Mi chiamo Elara, una creatura antica che vive nel cuore del mondo." | ⚡ Più veloce, qualità sorprendente. Tende a inventare nomi propri. |
| `qwen2.5:0.5b` | 400 MB | 9.23 | 24.52 | "Mi chiamo Qwen e sono stato creato da Alibaba Cloud..." | ❌ Rompe il personaggio |
| `qwen3:0.6b` | 520 MB | 7.28 | 23.07 | "Sono un mistero che non mi spiega." | ✅ Concisa e atmosferica |
| `gemma3:1b` | 815 MB | 5.11 | 12.53 | "Sono il ricordo di un sogno dimenticato." | ⭐ Miglior qualità nella fascia accettabile |
| `qwen2.5:1.5b` | 1.0 GB | 3.97 | 8.45 | "Sono il tempo che scorre, rimane indifferente." | ✅ Ottima qualità ma sotto soglia accettabile |
| `smollm2:360m` | 230 MB | 5.00 | 29.53 | "Siamo l'alessandrini." | ❌ Incoerente |
| `qwen3:1.7b` | 1.4 GB | 2.95 | 7.68 | "Io sono il mistero del tempo, il creatore della luce, un universo senza fine." | 🐢 Troppo lento |
| `llama3.2:1b` | 1.3 GB | 2.83 | 11.60 | "Chi sono io, nel silenzio trovo la mia anima, ma il mio volto è nascosto nel vetro." | 🐢 Troppo lento |

## Soglia di accettabilità

L'utente ha indicato **4-5 tok/s** come soglia minima per uso locale. Modelli sopra soglia: `gemma3:270m`, `qwen2.5:0.5b`, `qwen3:0.6b`, `gemma3:1b`, `smollm2:360m`, `qwen2.5:1.5b` (al limite).

## Candidati finali per fallback locale

1. **`gemma3:1b`** — 5.1 tok/s, qualità top per uso "atmosferico/oracolare". Default raccomandato.
2. **`gemma3:270m`** — 11.5 tok/s, per quando serve reazione istantanea o se il sistema è sotto carico.
3. **`qwen3:0.6b`** — 7.3 tok/s, alternativa moderna se Gemma desse problemi.

## Note

- Tutti i tempi includono `load duration` solo nella prima esecuzione di ogni modello (modello freddo). A modello caldo le metriche `eval rate` qui riportate sono rappresentative.
- Le risposte con caratteri di controllo ANSI (`[?25l`, ecc.) sono dovute allo streaming dell'output di `ollama run`; nel testo finale sopra sono ripulite.
- Per il progetto reale, il modello sul Pi è solo **fallback secondario**: il PRIMARY è Ollama sul PC con RX 6800 via LAN.
