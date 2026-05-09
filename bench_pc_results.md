# Benchmark modelli Ollama PC

Hardware: RX 6800 16GB · Host: `http://192.168.1.100:11434`

Prompt: `Maestro, ho trovato una porta antica con tre rune sopra. Cosa significa?`

## Risultati (run 2 warm)

| Modello | tps | total s | ttft s | chars |
|---|---:|---:|---:|---:|
| `qwen3:8b` | 7.76 | 7.86 | 6.85 | 213 |
| `qwen3:14b` | 4.61 | 10.41 | 9.17 | 149 |
| `llama3.1:8b` | 3.86 | 10.61 | 10.02 | 161 |
| `mistral-nemo:12b` | 3.59 | 12.53 | 11.77 | 175 |
| `gemma3:12b` | 3.43 | 10.80 | 9.95 | 162 |
| `gemma4:latest` | 2.86 | 23.45 | 22.62 | 252 |

## Output di esempio

### qwen3:8b

> Le rune sono antiche e segretamente legate al potere del tempo. La prima indica protezione, la seconda richiede un sacrificio, la terza apre porte a dimensioni non visibili. Sii cauto, o vieni assorbito dal vuoto.

### qwen3:14b

> Le rune segnano l'ingresso a un luogo sacro. Solo chi possiede la volontà pura e il cuore sincero può attraversarla. Sii prudente, il passato veglia.

### llama3.1:8b

> "Sagace esploratore, le rune su quella porta indicano una condizione: chi attraversa deve essere pronto per la verità oscura o la luce radiante che giace oltre."

### mistral-nemo:12b

> Le rune sulla porta antica indicano un incanto di protezione e avvertono dell'esistenza di un pericoloso ostacolo oltre la soglia. Procedete con cautela, valoroso esploratore.

### gemma3:12b

> Le rune narrano di passato, presente e futuro. Osserva attentamente i loro intrecci per comprendere il varco che si apre. La loro interpretazione rivelerà la via.

### gemma4:latest

> Quegli antichi sigili non sono semplici segni, ma un congiungimento di tre forze elementali. Devono essere attivati nell'ordine della Luce, dell'Ombra e del Silenzio per aprirti il passaggio. Solo l'armonia di tali tre forze ti guiderà oltre la soglia.

