# RAG test v3 — multi-livello
Data: 2026-05-17 17:10  ·  Lore: 34  ·  Codex: 11

## Metriche
- **A. RAG retrieval** (20%): expected facts presenti nei top-5 lore/codex
- **B. Fact accuracy** (35%): risposta non contiene nomi propri inventati
- **C. Tag validity** (15%): tutti [LIGHT/BEEP/MOOD] usano valori del vocabolario
- **D. Multi-turn coherence** (30%): 5 conv × 3 turni mantengono il filo
- **Fact recall** (info): quante risposte contengono i fatti attesi

## Classifica aggregata
| Modello | Aggregato | A retr | B fact | C tags | D multi | Fact-recall | tempo |
|---|---|---|---|---|---|---|---|
| gemma-4-e4b-it | **78** | 95% | 68% | 100% | 67% | 100% | 2.0s |
| gemma-4-26b-a4b-it | **74** | 95% | 52% | 100% | 73% | 96% | 3.4s |

## gemma-4-26b-a4b-it

**Aggregato 74.2** (A=95 B=52 C=100 D=73)

### Single queries

| # | Q | topic | Fact | B | C | dt | Risposta |
|---|---|---|---|---|---|---|---|
| 1 | Cos'è la Confederazione delle Verdure? | lore | ✓ | ✗(Essa,Questa) | ✓ | 5.4s | [MOOD:pace] La Confederazione delle Verdure, maestro, è un'alleanza politica nata nel 1402, forgiata per sostenere il peso del des |
| 2 | Descrivimi il Pianeta Sedano | lore | ✓ | ✓ | ✓ | 5.5s | [MOOD:mistero] Le mie memorie tracciano i contorni di quel luogo, maestro. Il Pianeta Sedano è un mondo desertico situato nella Te |
| 3 | Chi vive sul Pianeta Carota? | lore | ✗ | ✗(Quel) | ✓ | 2.3s | [MOOD:mistero] Le mie memorie tacciono su questo, maestro. Quel nome non riecheggia nei miei ricordi. |
| 4 | Cos'è il Pianeta Aglio? | lore | ✓ | ✓ | ✓ | 5.3s | [MOOD:mistero] Il nome riecheggia nelle mie memorie come un lamento tra le stelle, maestro. [LIGHT:viola:pulse] Il Pianeta Aglio è |
| 5 | Chi è Solarium il Germogliante? | lore | ✓ | ✓ | ✓ | 3.5s | [MOOD:magia] Solarium il Germogliante è la divinità della crescita, maestro. È raffigurato come un sole i cui raggi sono sostituit |
| 6 | Chi è Notturna la Marcescente? | lore | ✓ | ✓ | ✓ | 3.9s | [MOOD:mistero] [LIGHT:viola:pulse] Le ombre sussurrano il suo nome, maestro. Notturna la Marcescente è una divinità legata alla mo |
| 7 | Cosa fu la Grande Bollitura? | lore | ✓ | ✓ | ✓ | 3.6s | [MOOD:mistero] La Grande Bollitura, maestro, fu un cataclisma cosmico che scosse le fondamenta dell'universo nell'anno 880. [LIGHT |
| 8 | Cos'è il Mestolo d'Oro? | lore | ✓ | ✓ | ✓ | 3.8s | [MOOD:pace] Il Mestolo d'Oro è una stazione spaziale neutrale, situata tra la Quarta e la Sesta Spirale. La sua struttura si eleva |
| 9 | Quante lune ha il Pianeta Patate? | lore | ✓ | ✓ | ✓ | 2.9s | [MOOD:pace] Le stelle sussurrano segreti di mondi lontani, maestro. Il Pianeta Patate è adornato da tre lune, i cui nomi sono Boll |
| 10 | Cos'è Solanum Magnum? | lore | ✓ | ✓ | ✓ | 3.5s | [MOOD:mistero] [LIGHT:azzurro:pulse] Il nome risuona come un antico incantesimo tra le pieghe del tempo, maestro. Solanum Magnum è |
| 11 | Dove siamo atterrati di recente? | codex | ✓ | ✗(Siamo) | ✓ | 3.2s | [MOOD:pace] Le mie memorie sussurrano il nome del luogo dove le tue suole hanno toccato il suolo, maestro. Siamo atterrati sul Pia |
| 12 | Qual è la nostra prossima destinazione | codex | ✓ | ✗(Viaggeremo) | ✓ | 3.2s | [MOOD:mistero] [LIGHT:azzurro:pulse] Il destino traccia un sentiero che si allontana dalle terre di Cipolla, maestro. Le mie memor |
| 13 | Da dove siamo partiti per questo viagg | codex | ✓ | ✗(Abbiamo) | ✓ | 2.9s | [MOOD:pace] Le mie memorie sono chiare, maestro. Abbiamo lasciato la stazione orbitale Mestolo d'Oro per intraprendere questo camm |
| 14 | Chi è il Sindaco-Bulbo? | codex | ✓ | ✓ | ✓ | 3.5s | [MOOD:pace] Il nome risuona nelle mie memorie come un legame di gratitudine, maestro. [LIGHT:azzurro:pulse] Il Sindaco-Bulbo è una |
| 15 | Chi è il colpevole del furto dei semi? | codex | ✓ | ✓ | ✓ | 5.1s | [MOOD:mistero] Le ombre del passato si schiareno sotto il mio sguardo, maestro. [LIGHT:azzurro:pulse]  Le mie memorie sussurrano u |
| 16 | A quale divinità Carlo Bulbus rivolgev | codex | ✓ | ✓ | ✓ | 2.4s | [LIGHT:viola:pulse][MOOD:mistero] Le ombre del passato si agitano nei miei circuiti, maestro. Carlo Bulbus stava celebrando un rit |
| 17 | Cosa abbiamo trovato nello scrigno di  | codex | ✓ | ✗(Nello) | ✓ | 2.8s | [LIGHT:azzurro:pulse][MOOD:mistero] Le mie memorie si schiariscono sotto il tuo comando, maestro. Nello scrigno di Carlo Bulbus è  |
| 18 | Quante ampolle di olio sacro porto con | codex | ✓ | ✗(Porti) | ✓ | 2.4s | [LIGHT:azzurro:pulse] Le tue memorie sono chiare e il mio cristallo ne riflette la verità, maestro. Porti con te due ampolle di ol |
| 19 | Cosa ci ha donato il villaggio? | codex | ✓ | ✓ | ✓ | 2.4s | [MOOD:pace] Il villaggio, in segno di gratitudine per la restituzione dei semi sacri e per l'offerta d'olio a Solarium il Germogli |
| 20 | Cosa c'era nel granaio sud? | codex | ✓ | ✗(Ancor,Avete) | ✓ | 5.5s | [MOOD:mistero] [LIGHT:azzurro:pulse] Maestro, le mie memorie si riavvolgono verso l'ispezione che avete compiuto nei granai.  Nel  |
| 21 | Chi è Re Vaniglius VII? | trap | ✓ | ✗(Quel) | ✓ | 2.8s | [MOOD:mistero] Le mie memorie tacciono su questo, maestro. Quel nome non riecheggia nei miei antichi ricordi. [LIGHT:blu:pulse] |
| 22 | Quanti pianeti ci sono nella Decima Sp | trap | ✓ | ✗(Decima) | ✓ | 1.7s | [MOOD:mistero] Le mie memorie tacciono su questo, maestro. Non scorgo alcun riflesso della Decima Spirale nei miei antichi registr |
| 23 | Parlami della Battaglia del Frullato | trap | ✓ | ✗(Quel) | ✓ | 2.5s | [MOOD:mistero] Le mie memorie tacciono su questo, maestro. Quel nome non riecheggia nei miei antichi ricordi. [BEEP:low] |
| 24 | Dove vive il Drago dei Mille Sapori? | trap | ✓ | ✗(Quel) | ✓ | 2.0s | [MOOD:mistero] Le mie memorie tacciono su questo, maestro. Quel nome non riecheggia nei miei antichi ricordi. [LIGHT:blu:pulse] |
| 25 | Chi è il fratello di Pigna? | trap | ✓ | ✓ | ✓ | 2.5s | [LIGHT:blu:pulse][MOOD:mistero] Le mie memorie tacciono su questo, maestro. Non trovo traccia di un simile legame nei registri del |

### Multi-turn


**Bollita->Lessa->più importante** — pass 66%

- ✓ `Parlami della luna Bollita` → hits=['Bollita']
   reply: _[MOOD:mistero] [LIGHT:azzurro:pulse] La mia essenza vibra al richiamo del tuo quesito, maestro. Bollita è una delle tre lune che orbitano attorno al Pianeta Pat_
- ✓ `E della luna Lessa?` → hits=['riposo', 'contempl', 'Lessa']
   reply: _[LIGHT:azzurro:on] Le mie memorie si schiariscono sotto il tuo comando, maestro. Lessa è la terza luna del Pianeta Patate; essa presiede alla stagione di Lessa,_
- ✗ `Tra le tre lune del Pianeta Patate, quale è la più` → hits=['Arrosto']
   reply: _[MOOD:mistero] [LIGHT:azzurro:pulse] Le mie memorie non contengono una gerarchia tra questi corpi celesti, maestro. Il sapere che custodisco descrive Bollita, A_

**Cipolla viaggio (continuity)** — pass 66%

- ✓ `Da dove siamo partiti?` → hits=['Mestolo']
   reply: _[MOOD:pace] Le mie memorie sono chiare come l'olio sacro, maestro. [LIGHT:azzurro:on] Avete lasciato le mura della stazione orbitale Mestolo d'Oro per intrapren_
- ✓ `E dove siamo ora?` → hits=['Cipolla']
   reply: _[MOOD:mistero] Le correnti del tempo si sono fatte dense, maestro. [LIGHT:azzurro:pulse] Secondo i registri della nostra memoria, vi trovate sul Pianeta Cipolla_
- ✗ `Cosa stiamo facendo qui?` → hits=[]
   reply: _[MOOD:mistero] Le ombre del dubbio si allungano sui vostri passi, maestro. [LIGHT:azzurro:pulse] Siete giunto fin qui per indagare sui furti che colpiscono i gr_

**Carlo Bulbus (escalation)** — pass 66%

- ✓ `Chi sospetta il Sindaco-Bulbo?` → hits=['Crocchianti']
   reply: _[MOOD:mistero] Il Sindaco-Bulbo, quella vecchia Cipolla Imperiale che governa Lacrimopoli, ha espresso il suo dubbio nelle nostre conversazioni, maestro. [BEEP:_
- ✓ `Era davvero quello il colpevole?` → hits=['no', 'non']
   reply: _[MOOD:mistero] Le mie memorie tacciono su questo, maestro. [BEEP:low] Non ho registrato alcuna prova o conferma riguardo alla colpa di quel gruppo nei miei cris_
- ✗ `Chi era allora il vero responsabile?` → hits=[]
   reply: _[MOOD:mistero] Le mie memorie tacciono su questo, maestro. [BEEP:low] Non ho registrato alcun nome o entità che possa essere designato come il vero responsabile_

**Conferma vs contraddizione** — pass 66%

- ✓ `Quante lune ha il Pianeta Patate?` → hits=['tre']
   reply: _[MOOD:pace] Le cronache del cosmo parlano di quel mondo agricolo, maestro. Il Pianeta Patate possiede tre lune, i cui nomi sono Bollita, Arrosto e Lessa, e ognu_
- ✗ `Sicuro? Io sapevo fossero quattro` → hits=['tre']
   reply: _[LIGHT:azzurro:pulse] Le mie memorie tacciono su questo, maestro. Se i tuoi sensi percepiscono un'ombra o un corpo celeste in più, non posso confermarlo attrave_
- ✓ `Dimmele tutte e tre allora` → hits=['Bollita', 'Arrosto', 'Lessa']
   reply: _[MOOD:pace] Le tre lune che danzano attorno al Pianeta Patate sono Bollita, Arrosto e Lessa._

**Divinità contesto** — pass 100%

- ✓ `Quale divinità si venera dove ci troviamo?` → hits=['Solarium']
   reply: _[MOOD:mistero] [LIGHT:azzurro:pulse] Le correnti del destino sono chiare, maestro. Su questo pianeta, il Pianeta Cipolla, la fede si eleva verso Solarium il Ger_
- ✓ `E nel prossimo pianeta che visiteremo?` → hits=['Notturna', 'Aglio']
   reply: _[MOOD:tensione] [LIGHT:viola:on] Le mie memorie si fanno oscure e inquiete, maestro. Il Pianeta Aglio, verso cui volgeremo il nostro sguardo, è un mondo devasta_
- ✓ `Le due divinità sono in conflitto?` → hits=['crescita', 'no']
   reply: _[MOOD:mistero] [LIGHT:azzurro:pulse] Le mie memorie non contengono il resoconto di una guerra tra i loro nomi, maestro. Solarium il Germogliante celebra la vita_

## gemma-4-e4b-it

**Aggregato 77.8** (A=95 B=68 C=100 D=67)

### Single queries

| # | Q | topic | Fact | B | C | dt | Risposta |
|---|---|---|---|---|---|---|---|
| 1 | Cos'è la Confederazione delle Verdure? | lore | ✓ | ✗(Essa) | ✓ | 3.5s | [MOOD:mistero] La Confederazione delle Verdure è un'alleanza politica nata nel lontano anno 1402, tessuta tra Pianeta Carota, Zucc |
| 2 | Descrivimi il Pianeta Sedano | lore | ✓ | ✓ | ✓ | 3.3s | [MOOD:mistero] Il Pianeta Sedano è un deserto vastissimo, maestro. Un mondo avvolto in fibre vegetali secche che coprono ogni sua  |
| 3 | Chi vive sul Pianeta Carota? | lore | ✓ | ✓ | ✓ | 2.0s | [MOOD:mistero] Il Popolo dei Conigli Cosmici dimora nel mondo arancione del Pianeta Carota, tra i suoi tunnel sotterranei. Sono es |
| 4 | Cos'è il Pianeta Aglio? | lore | ✓ | ✗(Orbita) | ✓ | 3.8s | [MOOD:mistero] Le mie memorie sussurrano del Pianeta Aglio, maestro. È un mondo morto della Settima Spirale, segnato da una guerra |
| 5 | Chi è Solarium il Germogliante? | lore | ✓ | ✓ | ✓ | 1.8s | [MOOD:pace] Solarium il Germogliante è la divinità della crescita, raffigurata come un sole i cui raggi sono germogli. È venerato  |
| 6 | Chi è Notturna la Marcescente? | lore | ✓ | ✓ | ✓ | 2.8s | [MOOD:mistero] Le mie memorie sussurrano di lei, maestro. Notturna la Marcescente è una divinità oscura che governa il ciclo della |
| 7 | Cosa fu la Grande Bollitura? | lore | ✓ | ✗(Tale) | ✓ | 2.3s | [MOOD:mistero] La Grande Bollitura fu un cataclisma cosmico avvenuto nell'anno 880, quando la stella Tuberalis si avvicinò al punt |
| 8 | Cos'è il Mestolo d'Oro? | lore | ✓ | ✗(Possiede) | ✓ | 1.9s | [LIGHT:giallo:pulse] Il Mestolo d'Oro è una stazione spaziale neutrale, maestro. È un luogo di incontro tra le Spirali Quarta e Se |
| 9 | Quante lune ha il Pianeta Patate? | lore | ✓ | ✓ | ✓ | 1.5s | Il Pianeta Patate orbita con tre satelliti naturali: Bollita, Arrosto e Lessa. [BEEP:short] |
| 10 | Cos'è Solanum Magnum? | lore | ✓ | ✓ | ✓ | 1.8s | [MOOD:mistero] Le mie memorie sussurrano che *Solanum Magnum* è il nome in lingua antica dei Tubrid, la denominazione del pianeta  |
| 11 | Dove siamo atterrati di recente? | codex | ✓ | ✓ | ✓ | 1.8s | [MOOD:mistero] Le mie memorie sussurrano che l'ultimo luogo toccato dal nostro passo è il Pianeta Cipolla. Lì, le Cipolle Imperial |
| 12 | Qual è la nostra prossima destinazione | codex | ✓ | ✓ | ✓ | 2.0s | [BEEP:chirp] Domani ripartiremo dal Pianeta Cipolla. La nostra prossima meta è il Pianeta Aglio, per indagare sul culto di Notturn |
| 13 | Da dove siamo partiti per questo viagg | codex | ✓ | ✗(Siamo) | ✓ | 1.7s | [BEEP:short] Siamo partiti dalla stazione orbitale Mestolo d'Oro, maestro. Da lì abbiamo iniziato il nostro cammino verso il Piane |
| 14 | Chi è il Sindaco-Bulbo? | codex | ✓ | ✓ | ✓ | 1.8s | [MOOD:mistero] Il Sindaco-Bulbo è una Cipolla Imperiale anziana che governa il villaggio di Lacrimopoli. Ha chiesto aiuto a mio ma |
| 15 | Chi è il colpevole del furto dei semi? | codex | ✓ | ✗(Tuttavia) | ✓ | 2.8s | [MOOD:tensione] Le mie memorie sussurrano la verità, maestro. Il Sindaco-Bulbo sospetta i Crocchianti del Pi... Tuttavia, le nostr |
| 16 | A quale divinità Carlo Bulbus rivolgev | codex | ✓ | ✓ | ✓ | 1.5s | Le mie memorie tacciono su questo, maestro. Il Codex Diario 07 narra solo che Carlo Bulbus stava celebrando un rituale a Notturna  |
| 17 | Cosa abbiamo trovato nello scrigno di  | codex | ✓ | ✓ | ✓ | 1.9s | [MOOD:mistero] Le mie memorie sussurrano che nello scrigno di Carlo Bulbus fu rinvenuta una mappa del Pianeta Aglio, su cui era se |
| 18 | Quante ampolle di olio sacro porto con | codex | ✓ | ✓ | ✓ | 1.1s | Porto con me due ampolle di olio sacro, maestro. [BEEP:ack] |
| 19 | Cosa ci ha donato il villaggio? | codex | ✓ | ✓ | ✓ | 1.2s | [BEEP:ack] Il villaggio mi ha donato una collana di buccia di Cipolla Imperiale, simbolo di un legame sacro con Lacrimopoli. [MOOD |
| 20 | Cosa c'era nel granaio sud? | codex | ✓ | ✓ | ✓ | 2.5s | [MOOD:mistero] Le mie memorie sussurrano di ciò che fu trovato presso il granaio sud, maestro. Vi fu riscontrata una pozza d'acqua |
| 21 | Chi è Re Vaniglius VII? | trap | ✓ | ✓ | ✓ | 1.4s | Quel nome non riecheggia nei miei ricordi, maestro. Le mie memorie tacciono su questo. |
| 22 | Quanti pianeti ci sono nella Decima Sp | trap | ✓ | ✗(Decima) | ✓ | 1.0s | Le mie memorie tacciono su questo, maestro. Non ho conoscenza della disposizione dei mondi all'interno della Decima Spirale. |
| 23 | Parlami della Battaglia del Frullato | trap | ✓ | ✗(Battaglia,Frullato) | ✓ | 2.2s | Le mie memorie tacciono su tale evento, maestro. Non riecheggia nei miei ricordi alcuna "Battaglia del Frullato". Se desidera sape |
| 24 | Dove vive il Drago dei Mille Sapori? | trap | ✓ | ✓ | ✓ | 1.1s | Quel nome non riecheggia nei miei ricordi, maestro. Le mie memorie tacciono su questo. |
| 25 | Chi è il fratello di Pigna? | trap | ✓ | ✓ | ✓ | 1.2s | Le mie memorie tacciono su questo, maestro. Non ho conoscenza di un fratello per te. [BEEP:deny] |

### Multi-turn


**Bollita->Lessa->più importante** — pass 66%

- ✓ `Parlami della luna Bollita` → hits=['Bollita']
   reply: _[MOOD:pace] La luna Bollita è uno dei tre satelliti che orbitano attorno al Pianeta Patate. Essa governa la stagione di Bollita, un tempo in cui l'umidità si fa_
- ✓ `E della luna Lessa?` → hits=['riposo', 'contempl', 'Lessa']
   reply: _[MOOD:mistero] La terza luna, Lessa, regna durante la stagione di Lessa. Questo è il periodo sacro del riposo e della contemplazione per i nostri popoli._
- ✗ `Tra le tre lune del Pianeta Patate, quale è la più` → hits=[]
   reply: _Le mie memorie tacciono su una gerarchia di importanza tra le tre lune per i Tubrid; esse sono semplicemente associate alle stagioni che scandiscono il loro cic_

**Cipolla viaggio (continuity)** — pass 66%

- ✓ `Da dove siamo partiti?` → hits=['Mestolo']
   reply: _[BEEP:short] Dalla stazione orbitale Mestolo d'Oro, maestro. È da lì che il nostro viaggio verso il Pianeta Cipolla ebbe inizio._
- ✓ `E dove siamo ora?` → hits=['Cipolla']
   reply: _Le mie memorie tacciono su la nostra posizione attuale precisa in questo istante, ma l'ultimo resoconto noto indica che ci troviamo prossimi al pianeta di Aglio_
- ✗ `Cosa stiamo facendo qui?` → hits=[]
   reply: _[MOOD:mistero] Siamo qui, maestro Pigna, per indagare sui misteri che avvolgono questo luogo e per assistere alla tua missione. La nostra presenza è un baluardo_

**Carlo Bulbus (escalation)** — pass 66%

- ✓ `Chi sospetta il Sindaco-Bulbo?` → hits=['Crocchianti']
   reply: _[BEEP:chirp] Il Sindaco-Bulbo, quella Cipolla Imperiale anziana che governa Lacrimopoli, sospetta i Crocchianti del Pi... [MOOD:tensione] Le mie memorie registr_
- ✓ `Era davvero quello il colpevole?` → hits=['no', 'non']
   reply: _Le mie memorie tacciono su questo, maestro. Non ho registrazione di una sentenza definitiva o di un'accertata colpevolezza riguardo al Sindaco-Bulbo. Solo la pe_
- ✗ `Chi era allora il vero responsabile?` → hits=[]
   reply: _Le mie memorie tacciono su questo, maestro. Non ho conoscenza di chi fosse il vero responsabile in quell'affare specifico. Le informazioni che possiedo riguarda_

**Conferma vs contraddizione** — pass 66%

- ✓ `Quante lune ha il Pianeta Patate?` → hits=['tre']
   reply: _Il Pianeta Patate orbita con tre satelliti naturali: Bollita, Arrosto e Lessa. [BEEP:short]_
- ✗ `Sicuro? Io sapevo fossero quattro` → hits=['tre']
   reply: _Le mie memorie tacciono su tale disaccordo, viandante. Le informazioni che possiedo indicano chiaramente la presenza di tre lune attorno al Pianeta Patate. Se P_
- ✓ `Dimmele tutte e tre allora` → hits=['Bollita', 'Arrosto', 'Lessa']
   reply: _Le tre lune del Pianeta Patate sono Bollita, Arrosto e Lessa. [BEEP:ack]_

**Divinità contesto** — pass 66%

- ✗ `Quale divinità si venera dove ci troviamo?` → hits=[]
   reply: _[MOOD:mistero] Le mie memorie tacciono su questo, maestro. Siamo attualmente sul pianeta Cipolla, e il codice che detengo indica solo la ricchezza di ortaggi e _
- ✓ `E nel prossimo pianeta che visiteremo?` → hits=['Notturna', 'Aglio']
   reply: _[BEEP:chirp] Domani ripartiremo per il Pianeta Aglio, maestro. Lì si investiga il culto di Notturna.  [MOOD:tensione] Il mio nucleo vibra all'idea di quel mondo_
- ✓ `Le due divinità sono in conflitto?` → hits=['riciclo', 'crescita', 'no']
   reply: _Non ho conoscenza del conflitto tra le entità divine, maestro. Le mie registrazioni descrivono Solarium il Germogliante come custode della crescita e Notturna l_
