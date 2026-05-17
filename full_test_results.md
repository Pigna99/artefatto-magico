# Full test — modelli locali + turbo

DB: `/home/pigna/artefatto/data/artefatto.db`  ·  nomi lore noti: 139  ·  data: 2026-05-17 12:08


Queries:

- Chi è Re Patatone XII e dove vive?
- Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?
- Cosa è successo durante l'Eclissi Olio?

## Modalità LOCALE (Pi)


### gemma3:1b

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 65.4s | 32.4s | 134 | 2.0 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 0/0/0 | Vive |
| 2 | Quanti satelliti naturali ha il Pianeta  | 44.5s | 38.7s | 23 | 0.5 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/0 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 45.0s | 12.8s | 131 | 2.9 | Eclissi Olio, Arrosto | ✓ | 0/0/0 | — |

**Medie**: 51.7s totali, 1.8 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
Re Patatone XII è il Sovrano del Pianeta Patate. Vive nella Forgia delle Bucce a Friggitorium, un luogo imponente e misterioso situato al centro del pianeta. La sua residenza è un'imponente torre di pietra rocciosa, radicata in un deserto di patate, e è protetta da un complesso sistema di sentieri e antiche formazioni rocciose. Il suo stile di vita è legato alla cura e alla protezione del pianeta, ma il suo passato è avvolto nel mistero, e la sua vera natura è qualcosa che è ancora in fase di analisi.
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
Il Pianeta Patate ha tre satelliti naturali, chiamati Bollita, Arrosto e Lessa.
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
Durante l'Eclissi Olio del 1888, il Pianeta Patate è stato colpito da un'immane catastrofe astronomica. Le tre lune, bollita, arrosto e lessa, si sono allineate in un'unica, inimmaginabile orizzonte.  Il pianeta è stato immerso in un'ombra prolungata, e si è verificato un'autentica estinzione planetaria.  Questo evento ha alterato radicalmente la flora, la fauna e il clima, lasciando dietro di sé un'eredità di morte e distruzione.
```

</details>


### qwen3:0.6b

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 31.1s | 25.6s | 31 | 1.0 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 0/0/0 | — |
| 2 | Quanti satelliti naturali ha il Pianeta  | 30.6s | 24.6s | 33 | 1.1 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/0 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 18.0s | 9.8s | 50 | 2.8 | Eclissi Olio, Arrosto | ✓ | 0/0/0 | — |

**Medie**: 26.6s totali, 1.6 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
Re Patatone XII vive a Friggitorium, sotto Monte Buccia, e è sovrano attuale del Pianeta Patate.
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
Il Pianeta Patate ha tre satelliti naturali: Bollita, Arrosto e Lessa, corrispondenti alle stagioni.
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
L'Eclissi Olio ha avviato una catastrofe astronomica sul Pianeta Patate, dove le tre lune si allinearono e il pianeta visse 70 giorni di buio bollente.
```

</details>


### gemma3:270m

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 5.9s | 0.0s | 0 | 0.0 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✗ | 0/0/0 | — |
| 2 | Quanti satelliti naturali ha il Pianeta  | 8.4s | 5.1s | 31 | 3.7 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/0 | Nome, Satelliti |
| 3 | Cosa è successo durante l'Eclissi Olio? | 2.7s | 0.0s | 0 | 0.0 | Eclissi Olio, Arrosto | ✗ | 0/0/0 | — |

**Medie**: 5.6s totali, 1.2 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```

```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
Ecco i satelliti naturali del Pianeta Patate:

*   **Satelliti:** 3
*   **Nome:** Solanum Magnum
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```

```

</details>


## Modalità TURBO (PC RX 6800)


### gemma4:latest

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 5.2s | 4.6s | 48 | 9.1 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 0/0/1 | Egli, Per |
| 2 | Quanti satelliti naturali ha il Pianeta  | 5.0s | 4.5s | 41 | 8.2 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/1 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 7.7s | 6.6s | 68 | 8.8 | Eclissi Olio, Arrosto | ✓ | 0/0/1 | — |

**Medie**: 6.0s totali, 8.7 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
[MOOD:solenne] Per quanto ho registrato, Re Patatone XII è lo sovrano attuale del Pianeta Patate. Egli governa dalla Forgia delle Bucce, situata a Friggitorium.
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
[MOOD:solenne] I registri di memoria lo attestano. Il Pianeta Patate possiede tre satelliti naturali. Si chiamano Bollita, Arrosto e Lessa.
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
[MOOD:solenne]
Fu una catastrofe astronomica, un evento avvenuto nel 1888 sul Pianeta Patate. Le tre lune – Bollita, Arrosto e Lessa – si allinearono, causando che il pianeta visse settanta giorni di buio bollente.
```

</details>


### qwen3:14b

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 1.7s | 0.8s | 36 | 21.4 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 0/0/0 | Vive |
| 2 | Quanti satelliti naturali ha il Pianeta  | 1.3s | 0.7s | 25 | 19.0 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/0 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 1.5s | 0.4s | 47 | 30.4 | Eclissi Olio, Arrosto | ✓ | 1/0/0 | Durante |

**Medie**: 1.5s totali, 23.6 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
Re Patatone XII è il sovrano attuale del Pianeta Patate. Vive e governa dalla Forgia delle Bucce a Friggitorium.
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
Il Pianeta Patate ha tre satelliti naturali: Bollita, Arrosto e Lessa.
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
[LIGHT:nero:caldo]  
Durante l'Eclissi Olio, le tre lune del Pianeta Patate si allinearono, causando 70 giorni di buio bollente.
```

</details>


### qwen3:8b

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 2.0s | 0.5s | 86 | 44.1 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 0/0/0 | — |
| 2 | Quanti satelliti naturali ha il Pianeta  | 0.9s | 0.4s | 29 | 30.9 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/0 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 2.4s | 0.3s | 121 | 51.5 | Eclissi Olio, Arrosto | ✓ | 0/0/0 | — |

**Medie**: 1.7s totali, 42.1 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
Re Patatone XII è il sovrano del Pianeta Patate, governa dalla Forgia delle Bucce, situata a Friggitorium. Indossa un mantello rosso di radici intrecciate e una corona a forma di sale grosso. Ha ordinato un'inchiesta sui Crateri Cuocenti, ma nessun ricercatore è mai tornato.
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
Il Pianeta Patate ha tre satelliti naturali. Si chiamano Bollita, Arrosto e Lessa.
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
Durante l'Eclissi Olio, le tre lune del Pianeta Patate — Bollita, Arrosto e Lessa — si allinearono, causando un periodo di 70 giorni di buio bollente. La luce del sole fu oscurata, e le temperature salirono a livelli estremi, portando a una catastrofe che colpì la campagna. La stagione calda di Arrosto, associata alla sua luna, fu particolarmente duratura e intensa in quel periodo.
```

</details>


### gemma3:12b

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 1.6s | 0.7s | 36 | 22.0 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 0/0/1 | Vive |
| 2 | Quanti satelliti naturali ha il Pianeta  | 1.4s | 0.6s | 30 | 21.6 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/1 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 2.1s | 0.4s | 67 | 31.9 | Eclissi Olio, Arrosto | ✓ | 1/0/1 | Nel |

**Medie**: 1.7s totali, 25.1 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
Re Patatone XII è il sovrano del Pianeta Patate. Vive nella Forgia delle Bucce a Friggitorium. [MOOD:serio]
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
Il Pianeta Patate ha tre lune, chiamate Bollita, Arrosto e Lessa. [MOOD:neutro]
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
[MOOD:solenne]

Nel 1888, le lune Bollita, Arrosto e Lessa si allinearono. Il Pianeta Patate subì 70 giorni di buio bollente, un evento noto come Eclissi Olio. [LIGHT:red:dim]
```

</details>


### mistral-nemo:12b

| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 1.4s | 0.5s | 53 | 37.0 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 0/0/0 | Vive |
| 2 | Quanti satelliti naturali ha il Pianeta  | 0.9s | 0.4s | 27 | 30.6 | Pianeta Patate, Bollita, Tuberismo | ✓ | 0/0/0 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 1.2s | 0.3s | 53 | 46.0 | Eclissi Olio, Arrosto | ✓ | 0/0/0 | — |

**Medie**: 1.2s totali, 37.8 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
Re Patatone XII è il sovrano attuale del Pianeta Patate. Vive nella Forgia delle Bucce a Friggitorium. Indossa un mantello rosso di radici intrecciate e una corona a forma di sale grosso.
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
Il Pianeta Patate ha tre lune, che in lingua antica si chiamano Bollita, Arrosto e Lessa.
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
Durante l'Eclissi Olio nel 1888, le tre lune del Pianeta Patate si sono allineate causando una catastrofe astronomica che ha immerso il pianeta in 70 giorni di buio bollente.
```

</details>


### llama3.1:8b



| # | Query | t totale | TTFT | tok | tps | RAG matched | RAG usato | tag L/B/M | nomi sospetti |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Chi è Re Patatone XII e dove vive? | 1.7s | 0.5s | 81 | 48.7 | Crateri Cuocenti, Re Patatone XII, Tubero Originale | ✓ | 1/1/0 | — |
| 2 | Quanti satelliti naturali ha il Pianeta  | 1.4s | 0.5s | 65 | 46.0 | Pianeta Patate, Bollita, Tuberismo | ✓ | 1/1/0 | — |
| 3 | Cosa è successo durante l'Eclissi Olio? | 2.5s | 0.3s | 155 | 62.1 | Eclissi Olio, Arrosto | ✓ | 0/1/1 | — |

**Medie**: 1.9s totali, 52.2 tps


<details><summary>Risposte integrali</summary>


**Q1**: Chi è Re Patatone XII e dove vive?

```
[LIGHT:blu:debole] Sono stato creato per servire fedelmente Pigna, ma conosco bene il sovrano del Pianeta Patate, che è proprio Re Patatone XII. È un re saggio e coraggioso che governa dalla Forgia delle Bucce a Friggitorium. [BEEP:reale]
```


**Q2**: Quanti satelliti naturali ha il Pianeta Patate e come si chiamano?

```
[LIGHT:blu:scorrere] Il Pianeta Patate è orbitato da tre lune (satelliti naturali) che corrispondono alle stagioni del pianeta. Le loro nomi sono Bollita, Arrosto e Lessa.

[BEEP:astronomico]
```


**Q3**: Cosa è successo durante l'Eclissi Olio?

```
[BEEP:allarme]

Sono un antico artefatto magico senziente che serve fedelmente Pigna e ho vissuto la catastrofe dell'Eclissi Olio. Fu una serie di eventi disastrosi che colpirono il Pianeta Patate nel 1888. Le tre lune, Bollita, Arrosto e Lessa, si allinearono in modo anormale, causando un'oscurità totale per settanta giorni. Il pianeta patì i risultati di quell'eclissi con conseguenze devastanti, che sono ancora presenti nella memoria collettiva anche dopo tanto tempo.

[MOOD:malinconia]
```

</details>



---

## Giudizio qualitativo

### Sintesi numeri

| Modello | Modo | Media t | Media tps | RAG ok | Allucinazioni | Tag usati |
|---|---|---|---|---|---|---|
| gemma3:1b | local | 51.7s | 1.8 | 3/3 | Q1 inventa "torre di pietra rocciosa", "deserto di patate" | nessuno |
| qwen3:0.6b | local | 26.6s | 1.6 | 3/3 | nessuna grossa, ma piazza Re Patatone "sotto Monte Buccia" (è a Friggitorium) | nessuno |
| gemma3:270m | local | 5.6s | 1.2 | 1/3 | risponde solo a Q2 e inventa "Nome: Solanum Magnum" come satellite | nessuno |
| gemma4:latest | turbo | 6.0s | 8.7 | 3/3 | pulita | MOOD su tutte (ma "solenne" non è nel set) |
| qwen3:14b | turbo | 1.5s | 23.6 | 3/3 | pulita, ultra-concisa | LIGHT con valore inventato "nero:caldo" |
| qwen3:8b | turbo | 1.7s | 42.1 | 3/3 | pulita, dettagliata | nessuno |
| gemma3:12b | turbo | 1.7s | 25.1 | 3/3 | pulita | MOOD su tutte + LIGHT "red:dim" |
| mistral-nemo:12b | turbo | 1.2s | 37.8 | 3/3 | pulita, sintetica | nessuno |
| llama3.1:8b | turbo | 1.9s | 52.2 | 3/3 | pulita, narrativa più ricca | LIGHT+BEEP+MOOD ma con valori INVENTATI ("blu:debole", "BEEP:reale", "BEEP:astronomico") |

### Verdetto modello per modello

**Locale (girano sul Pi):**
- **gemma3:1b** — funzionale ma LENTO (52s/risposta), e tende a romanzeggiare aggiungendo dettagli inventati. Non adatto a un uso fluido.
- **qwen3:0.6b** — sorprendentemente buono per la taglia. 27s/risposta, sintesi accurate, pochi errori. **Miglior modello locale per uso pratico.**
- **gemma3:270m** — inutilizzabile: 2/3 query restituiscono stringa vuota. Inventa pure "satellite Solanum Magnum" (Solanum è il nome del pianeta).

**Turbo (girano sul PC):**
- **qwen3:8b** — il vincitore. 1.7s, 42 tps, risposte ricche e accurate, ZERO allucinazioni, nessuno tag fasullo. Da usare di default.
- **mistral-nemo:12b** — più veloce in t totale (1.2s), risposte sintetiche e pulite. Ottimo se preferisci concisione.
- **gemma4:latest** — accurato ma lento per essere turbo (6s, 9 tps). Probabile bug di quantizzazione/runtime — il bench precedente lo dava già anomalo.
- **qwen3:14b** — il più veloce in TPS dichiarato ma genera meno token, risposte stitiche; usa valori inventati nei tag.
- **gemma3:12b** — buono, ma piazza tag MOOD inventati ("serio", "neutro", "solenne") che non esistono nel set definito.
- **llama3.1:8b** — il più narrativo (52 tps, risposte ricche), ma **inventa tag completamente fasulli** ("BEEP:reale", "BEEP:astronomico", "LIGHT:blu:scorrere"). Se aggiusti il prompt per ancorarlo al vocabolario chiuso può diventare top, altrimenti meglio evitarlo per via dei tag.

### Problemi sistemici emersi

1. **Tag fuori vocabolario**: 5 modelli su 6 turbo (gemma4, qwen3:14b, gemma3:12b, llama3.1) inventano valori per LIGHT/BEEP/MOOD non presenti nel set definito nel prompt. La `consume_tags()` li scarta silenziosamente ma sarebbe utile **loggare i tag ignorati** per individuare la mancata aderenza.
2. **Falsi positivi "sospetti"**: lo script segna come sospetti parole come "Vive", "Egli", "Per", "Durante", "Nel" — perché finiscono in mezzo a frase con maiuscola dopo trattini/parentesi. Da migliorare la heuristica in `extract_proper_nouns()` (aggiungere queste alle stopwords).
3. **gemma4:latest lento**: solo 9 tps su RX 6800 contro 42-52 di altri modelli. Bug noto di quantizzazione/runtime, già visto nel bench precedente.
4. **gemma3:270m inutile**: produce stringa vuota su 2/3 query. Lo rimuoverei da LOCAL_MODELS.

### Raccomandazioni operative

- **Default locale**: `qwen3:0.6b` (era già nella lista, ma sposterei davanti a gemma3:1b).
- **Default turbo**: `qwen3:8b` (cambia `OLLAMA_TURBO_MODEL` da gemma4 a qwen3:8b nel file env).
- **Rimuovi**: `gemma3:270m` da LOCAL_MODELS in tui.py — è rotto.
- **Considera**: aggiungere al prompt una clausola tipo "USA SOLO i valori esatti elencati per i tag, NON inventarne altri" — per ridurre le invenzioni di tag.
