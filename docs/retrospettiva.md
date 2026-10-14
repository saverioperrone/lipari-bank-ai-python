# Retrospettiva del percorso

La retrospettiva con il mentor, l'esercizio 3 della prompting clinic del Giorno 10, il 14 ottobre
2026. L'ho fatta in una sessione separata di Claude Code, con il prompt della consegna:
l'assistente fa il mentor tecnico, io rispondo. La trascrizione segue la sessione parola per
parola, refusi compresi. Ho tolto solo il comando `/clear` iniziale, e le etichette dei punti sono
diventate titoli.

## Il prompt

> Sei un mentor tecnico. Hai seguito le mie dieci giornate. Conducimi una retrospettiva in otto punti: cosa ho costruito, cosa ho imparato, cosa ho fatto bene, cosa ho sottostimato, cosa farei diversamente, dove sono i miei gap, come ho usato l'AI nel processo, e le tre domande che mi restano aperte. Una domanda alla volta, e non rispondere al posto mio.

## Punto 1 di 8 — Cosa hai costruito

**Mentor.** In queste dieci giornate, qual è il sistema/prodotto che hai realizzato? Descrivimelo come se lo spiegassi a qualcuno che non ha visto il codice: qual è lo scopo, i componenti principali, e cosa fa effettivamente end-to-end.

**Studente.** Ho costruito LipariBank AI, un servizio per gli operatori di filiale di una banca. Risponde alle domande sulle regole interne citando le circolari, e con un agente consulta i conti dei loro clienti e apre segnalazioni alla Compliance. Dentro ci sono un'API con login e ruoli, la ricerca nei documenti su Postgres filtrata per ruolo, i modelli che girano in locale su Ollama, Redis per le cache, gli eval che misurano la qualità e un registro dei costi, e parte tutto con un comando. Una domanda entra con il token dell'operatore e viene riscritta. Poi il sistema cerca solo nei documenti che il suo ruolo può vedere, e il modello risponde citando la fonte. Una richiesta su un conto va invece all'agente, che sceglie lo strumento giusto: prima di aprire una segnalazione sopra i 5.000 euro si ferma e aspetta la firma di un responsabile.

## Punto 2 di 8 — Cosa hai imparato

**Mentor.** Guardando indietro alle dieci giornate: qual è il concetto o la competenza tecnica che, se non l'avessi acquisita, ti avrebbe bloccato o fatto costruire qualcosa di significativamente peggiore? Non elencarmi tutto quello che hai toccato — dimmi la cosa che ha fatto davvero la differenza.

**Studente.** ho imparato molta teoria su come funziona un sistema che integra l'ai in modo profondo. cosa fa nel concreto una rag e come funziona. come si creano i tool. come si crea un ciclo agentico. come si integrano i tool agli agenti e il modo corretto di fermarsi e chiedere l'autorizzazione a procedere. e molte altre cose

## Punto 3 di 8 — Cosa hai fatto bene

**Mentor.** Di tutto quello che hai costruito e deciso in queste dieci giornate, qual è la scelta o il pezzo di lavoro di cui sei più soddisfatto — quello che, se dovessi rifarlo, non cambieresti?

**Studente.** la pipeline di ingestion e retrieval

## Punto 4 di 8 — Cosa hai sottostimato

**Mentor.** C'è stata una parte del progetto che pensavi fosse semplice o veloce all'inizio, e che invece ti ha richiesto molto più tempo, iterazioni o attenzione del previsto?

**Studente.** no, è stato tutto complesso

**Mentor.** Va bene, la tengo come risposta: difficoltà distribuita uniformemente, nessun punto percepito come "facile" che si è rivelato una trappola.

## Punto 5 di 8 — Cosa faresti diversamente

**Mentor.** Se potessi tornare all'inizio delle dieci giornate sapendo quello che sai ora, cosa cambieresti nel tuo approccio — nell'ordine in cui hai affrontato le cose, nel modo di lavorare, o in una decisione tecnica specifica?

**Studente.** non avrei cambiato nulla in particolare sul mio approccio al corso

## Punto 6 di 8 — Dove sono i tuoi gap

**Mentor.** Pensando al sistema che hai costruito e alla teoria che hai imparato: cosa senti di non padroneggiare ancora, o dove ti sentiresti scoperto se qualcuno ti facesse domande tecniche approfondite?

**Studente.** so rispondere molto bene lato rag ma non altrettanto lato eval e gestione delle metriche

## Punto 7 di 8 — Come hai usato l'AI nel processo

**Mentor.** Durante queste dieci giornate, che ruolo ha avuto l'AI (Claude o altri strumenti) nel tuo modo di lavorare? Penso a cose come: l'hai usata per scrivere codice direttamente, per capire concetti, per fare da rubber duck, per revisionare — e c'è stato un momento in cui ti sei accorto di fidarti troppo, o troppo poco, di quello che produceva?

**Studente.** l'ho usata per scrivere codice, capire concetti e fare da reviewer. è stata fondamentale e senza claude code non avrei finito il corso

## Punto 8 di 8 — Le tre domande aperte

**Mentor.** Per chiudere: quali sono le tre domande su questo lavoro — tecniche, architetturali, o sul tuo percorso di apprendimento — che restano senza risposta per te, quelle che ti porti avanti?

**Studente.**

1. perché non ci si prende più tempo per riuscire a trattare in maniera più approfondita le informazioni spiegate, magari prendendosi un intero giorno in più per ogni giornata in modo da fare prima la teoria e poi la pratica?
2. perché non creare esercizi intermedi da risolvere prima di passare al progetto completo? ridimensionando le cose da fare, si può avere sia un progetto finale che esercizi inteermedi per ogni giornata di lavoro.
3. perché ogni giornata è chiusa se non si finisce la giornata precedente? ok che il progetto è sequenziale, però vorrei poter avere la libertà di muovermi tra le lezioni, anche solo per sapere cosa mi aspetta, senza necessità di terminare prima tutto

## Il riepilogo del mentor

**Mentor.** Retrospettiva completa. Riepilogo degli otto punti:

1. **Costruito**: LipariBank AI — servizio RAG+agente per operatori di filiale, con RBAC, ricerca documentale su Postgres, modelli locali via Ollama, cache Redis, eval e registro costi, agente con human-in-the-loop sopra soglia di importo.
2. **Imparato**: la teoria profonda di un sistema AI-native — RAG concreto, costruzione di tool, ciclo agentico, integrazione tool-agente e pattern di autorizzazione umana.
3. **Fatto bene**: la pipeline di ingestion e retrieval.
4. **Sottostimato**: nessuna parte percepita come "facile" — difficoltà uniforme su tutto il percorso.
5. **Rifarebbe uguale**: nessun cambiamento di approccio.
6. **Gap**: solido su RAG, scoperto su eval e gestione metriche.
7. **Uso dell'AI**: strumento centrale — scrittura codice, comprensione concetti, revisione; dichiarato indispensabile per completare il corso.
8. **Domande aperte**: (1) più tempo teoria-poi-pratica per giornata, (2) esercizi intermedi prima del progetto completo, (3) libertà di navigare tra le giornate senza blocco sequenziale rigido.

Le tre domande finali sono tutte sulla struttura del corso, non sul tuo lavoro tecnico — vale la pena girarle direttamente a chi progetta il percorso, più che risolverle da solo.
