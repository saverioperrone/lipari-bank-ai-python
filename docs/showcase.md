# Showcase — il copione

Lo showcase dura cinque minuti, con un formato fisso: «cinque minuti non perdonano». Per ogni
fase questo copione dice cosa è già pronto e cosa fai in scena. I comandi si lanciano da Git Bash,
nella cartella del progetto. Quelli della leva e della demo li ho provati il 12 ottobre sul
sistema acceso, e ho misurato i tempi. Gli altri vengono dal README, dove erano già stati provati.

## 1. Far partire il sistema

```bash
cd lipari-bank-ai
docker compose up -d              # la prima volta, o dopo un cambio di codice: docker compose up --build -d
docker compose ps -a              # api (healthy); migrate, modelli e seed: Exited (0)
curl -s localhost:8000/ready      # {"status":"ready","checks":{"database":"ok","cache":"ok"}}
bash scripts/smoke.sh             # dieci «ok» e «smoke: tutto a posto»
```

- Lo smoke test è verificato con la leva accesa, com'è consegnata: lancialo prima di spegnerla.
- Dopo un riavvio di Docker torna su solo l'api: se `/ready` risponde 503, lancia
  `docker compose up -d`.
- Per spegnere tutto: `docker compose down`. I dati restano nei volumi.

## 2. La leva: spegnerla e riaccenderla

La leva del Giorno 10 fa scrivere la risposta dell'advisor a un modello più piccolo,
`llama3.2:1b`. È accesa nel `.env`, con `ADVICE_MODEL=llama3.2:1b`. Spenta, l'advisor risponde con
`llama3.2:3b`, come prima. Tutto il resto non cambia: la ricerca, i permessi e l'agente.

```bash
ADVICE_MODEL= docker compose up -d --no-deps api   # spenta: l'advisor torna a llama3.2:3b
docker compose up -d --no-deps api                 # accesa: llama3.2:1b, come nel .env
docker compose exec api printenv ADVICE_MODEL      # vuoto = spenta; llama3.2:1b = accesa
```

- Il `.env` non cambia: il valore vuoto vale solo per quel comando.
- `--no-deps` riavvia solo l'api, che è pronta in 4-5 secondi.
- Funziona solo da Git Bash: in PowerShell la sintassi `VARIABILE= comando` non esiste.
- Appena spenta la leva, la prima risposta del modello grande arriva a freddo: 39 secondi, poi fra
  5 e 14. Per questo serve il riscaldamento.

| Momento | Leva | Perché |
|---|---|---|
| smoke test | accesa | è verificato così |
| demo dello showcase | spenta | le prime due parti della demo mostrano le citazioni: con la leva accesa l'advisor cita in 1 risposta su 30 |
| `misura_tetti`, per i numeri | accesa | il p95 della consegna è quello con la leva |
| dopo lo showcase | accesa | è la configurazione consegnata |

## 3. Dieci minuti prima

1. Controlla il sistema e lancia lo smoke test, con la leva accesa: sezione 1.
2. Spegni la leva, e controlla con `printenv` che sia vuota.
3. Prepara il terminale: incolla il blocco qui sotto. Prende i token di Marco, Giulia e Lucia e
   definisce i comandi della demo. Un token dura 30 minuti: incollalo non più di mezz'ora prima.
4. Apri questo file al diagramma a quattro riquadri.
5. Per ultimo, subito prima di cominciare, fai il riscaldamento, cioè la prima domanda della demo,
   una volta: `chiedi "$MARCO" "Quali controlli servono per un bonifico verso il Venezuela?"`.
   Ollama tiene il modello in memoria cinque minuti dopo l'ultima domanda (è il valore di default,
   e il compose non lo cambia), e la demo comincia al minuto 2: se il riscaldamento è fatto troppo
   presto, la prima risposta della demo torna a freddo.

```bash
B=http://localhost:8000
export PYTHONIOENCODING=utf-8
login() {
  curl -s -X POST $B/api/auth/login -d "username=$1&password=bootcamp" \
    | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
}
MARCO=$(login mbianchi); GIULIA=$(login grossi); LUCIA=$(login lverdi)
chiedi() {     # chiedi "$MARCO" "domanda": la risposta e i documenti citati
  curl -s -X POST $B/api/ai/advice -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"question\": \"$2\"}" \
    | python -c "import sys,json; d=json.load(sys.stdin); print(d['answer']); print('citati:', sorted({c['document_id'] for c in d['citations']}))"
}
agente() {     # agente "domanda": i passi, i tool, come si è fermato, la risposta
  ULTIMO=$(curl -s -X POST $B/api/ai/agent -H "Authorization: Bearer $MARCO" -H "Content-Type: application/json" \
    -d "{\"message\": \"$1\"}")
  echo "$ULTIMO" | python -c "import sys,json; d=json.load(sys.stdin); print('passi:', d['steps'], '| tool:', d['tool_calls'], '| fermato da:', d['stopped_by']); print(d['reply'])"
  RUN=$(echo "$ULTIMO" | python -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
}
traccia() {    # le righe agent_step dell'ultimo run, dal log dell'api
  docker compose logs api --since 5m --no-log-prefix | grep '"agent_step"' | grep "$RUN" \
    | python -c "import sys,json; [print('passo', d['step'], d['tool'], '->', d['result_kind'], f\"({d['duration_ms']} ms)\") for d in map(json.loads, sys.stdin)]"
}
in_attesa() {  # cosa vede Giulia della pratica sospesa
  curl -s $B/api/ai/agent/$RUN -H "Authorization: Bearer $GIULIA" \
    | python -c "import sys,json; d=json.load(sys.stdin); print(d['status'], '| chiesta da', d['requested_by']); print(d['description'])"
}
approva() {    # approva "$GIULIA" (o "$LUCIA", per la seconda firma): il run riprende
  curl -s -X POST $B/api/ai/agent/$RUN/approve -H "Authorization: Bearer $1" \
    | python -c "import sys,json; d=json.load(sys.stdin); print('passi:', d['steps'], '| tool:', d['tool_calls'], '| fermato da:', d['stopped_by']); print(d['reply'])"
}
```

Le domande sono scritte senza accenti, perché il curl di Git Bash li spedisce in una codifica che
il server non legge.

## 4. Il copione, minuto per minuto

| Tempo | Fase | Già pronto | In scena |
|---|---|---|---|
| 0:00–0:20 | chi sei e cos'hai costruito | il tuo nome e la frase della clinic | li dici |
| 0:20–1:00 | il problema, dal punto di vista di Marco | il testo, 98 parole | lo dici, senza schermo |
| 1:00–2:00 | l'architettura | i due diagrammi e il testo, 148 parole | mostri il diagramma a quattro e dici il testo |
| 2:00–4:00 | la demo | i comandi provati, con i tempi, e le battute | lanci i comandi, indichi la riga che conta, dici le battute |
| 4:00–4:40 | i tre numeri | il testo, 105 parole, e la tabella del metodo | dici il testo |
| 4:40–5:00 | cosa manca | il testo, 52 parole | lo dici, prima che te lo chiedano |

I tempi dei testi sono calcolati a 150 parole al minuto: nelle prove controllali con il cronometro.

### 0:00–0:20 — Chi sei e cos'hai costruito

**Già pronto.** La frase, dall'esercizio 1 della clinic:

> LipariBank AI è un assistente intelligente al servizio degli operatori in grado di rispondere
> alle tue domande sulla filiale basandosi sui documenti, sulle circolari e sulle fonti interne,
> riportandoli come citazione diretta quando possibile. Rispettando la privacy e la sicurezza,
> permette di consultare i conti dei clienti in portafoglio e aprire segnalazioni.

**Cosa dici.** «Sono Saverio Perrone.» Poi la frase, senza leggerla. Il nome copre il «chi sei»
del testo, perché la frase non lo contiene.

### 0:20–1:00 — Il problema, dal punto di vista di Marco

**Cosa chiede il testo.** «Il problema, dal punto di vista di Marco. Non l'architettura: la
persona e il suo problema.»

**In scena.** Niente schermo: lo dici guardando chi ascolta, senza nominare nessuna tecnologia.

**Cosa dici** (98 parole, circa 40 secondi):

> Vi presento Marco. Lavora allo sportello di una filiale, e ha davanti un cliente che vuole
> mandare 25.000 euro in Venezuela. Prima di dirgli sì o no, Marco deve sapere cosa dicono le
> regole della banca: la circolare sui bonifici esteri, l'elenco dei paesi a rischio, gli obblighi
> antiriciclaggio. Sono documenti diversi, e il cliente aspetta. Gli serve una risposta giusta,
> subito, con il riferimento alla regola, per poterla controllare. E c'è quello che non deve
> vedere: le istruttorie riservate della Compliance. Se poi l'operazione va segnalata, sopra i
> 5.000 euro non decide da solo: serve un responsabile.

### 1:00–2:00 — L'architettura in sessanta secondi

**Cosa chiede il testo.** «L'architettura in un diagramma e sessanta secondi. Cinque riquadri, non
quindici.» L'Architect's Mindset aggiunge come raccontarla: come un percorso, nell'ordine in cui
si muovono i dati, e non come un elenco di moduli in ordine di cartella. Il suo esempio: «arriva
una domanda, la riscriviamo perché gli operatori scrivono in fretta, cerchiamo nei documenti che
quel ruolo può vedere, e il modello risponde citando».

**Già pronto.** I due diagrammi dell'esercizio 2 della clinic.

Quello da mostrare, a quattro riquadri, con l'agente dentro MODELLI:

```
┌────────────────────────────────────────────────────────────────────────┐
│                                INGRESSO                                │
└────┬──────────────────────────────────────────────────────────────┬────┘
     │ richiesta e ruolo               richiesta, approva o rifiuta │
     ▼                                                              ▼
┌─────────┐ prompt ed embedding ┌────────────────────────────────────────┐
│ SERVIZI │────────────────────►│         MODELLI, con l'agente          │
└────┬────┘                     └────┬───────────────────────────────────┘
     │ passaggi filtrati per ruolo   │ costo di ogni chiamata,
     │                               │ conti, esecuzioni sospese
     ▼                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                                  DATI                                  │
└────────────────────────────────────────────────────────────────────────┘
```

Quello di partenza, a cinque riquadri, con l'agente separato. Tienilo pronto se ti chiedono dov'è
l'agente:

```
┌────────────────────────────────────────────────────────────────────────┐
│                                INGRESSO                                │
└────┬──────────────────────────────────────────────────────────────┬────┘
     │ richiesta e ruolo               richiesta, approva o rifiuta │
     ▼                                                              ▼
┌─────────┐ prompt ed embedding ┌─────────┐ quale tool chiamare ┌────────┐
│ SERVIZI │────────────────────►│ MODELLI │◄────────────────────│ AGENTE │
└────┬────┘                     └────┬────┘                     └───┬────┘
     │ passaggi filtrati per ruolo   │ costo di ogni chiamata       │
     │                               │    conti, esecuzioni sospese │
     ▼                               ▼                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                                  DATI                                  │
└────────────────────────────────────────────────────────────────────────┘
```

| Riquadro | Cosa contiene |
|---|---|
| INGRESSO | l'API, il login, i ruoli, le sonde, il limite di 15 richieste al minuto |
| SERVIZI | il RAG con la riscrittura, la ricerca filtrata per ruolo e le citazioni; l'ingest, la chat, le categorie, le segnalazioni |
| MODELLI | la scelta del modello, i prompt, le cache, i costi, gli eval; nel diagramma a quattro anche l'agente, con i suoi tool e l'approvazione umana |
| AGENTE | solo nel diagramma a cinque: il ciclo scritto a mano, i cinque tool, la sospensione per l'approvazione, il server MCP |
| DATI | Postgres con pgvector e Redis: utenti, clienti, conti, movimenti, passaggi, segnalazioni, esecuzioni sospese, costi, cache |

**In scena.** Mostri il diagramma a quattro riquadri e, mentre parli, segui le frecce:
dall'ingresso ai servizi e ai modelli, poi giù ai dati.

**Cosa dici** (148 parole, circa 60 secondi):

> Ecco il sistema, seguendo una domanda. Entra dall'ingresso: l'API riconosce Marco dal suo
> token, e da lì in poi ogni passo conosce il suo ruolo. Se chiede una regola, la domanda va ai
> servizi. Prima la riscriviamo, perché allo sportello si scrive in fretta. Poi cerchiamo nei
> documenti solo i passaggi che il suo ruolo può vedere: il filtro sta nella query sul database,
> non nel prompt. Infine il modello risponde citando la fonte. Se invece Marco chiede di agire su
> un conto, la domanda va al modello come agente: sceglie quale strumento usare, vede solo i conti
> dei clienti di Marco, e prima di aprire una segnalazione sopra soglia si ferma e aspetta la
> firma di un responsabile. Sotto, i dati: Postgres con i documenti, i conti e le pratiche
> sospese, e Redis per le cache. Parte tutto con un comando, e i modelli girano in locale.

### 2:00–4:00 — La demo

**Cosa chiede il testo.** «La demo, da docker compose up già avviato:
- una domanda all'advisor con la citazione;
- la stessa domanda con il token di Giulia che vede un documento in più;
- l'agente sulla domanda multi-step con la traccia dei passi;
- una segnalazione sopra soglia che si ferma in attesa.»

**Già pronto.**
- La leva è spenta e il terminale è preparato (sezione 3).
- Ogni comando qui sotto è stato provato, con il tempo misurato e la riga da indicare.
- Non improvvisare domande diverse. `llama3.2:3b` usa un tool per domanda: con una domanda che ne
  chiedeva due (i conti del cliente, poi il saldo), ha usato il primo e il saldo l'ha inventato,
  5.215,41 € invece di 48.200,00.

**In scena.** Lanci i comandi nell'ordine. Mentre il modello lavora dici la prima battuta; quando
arriva la risposta indichi la riga che conta e dici la seconda.

**Cosa dici, prima di cominciare.** «Il sistema è già acceso. Per la demo uso il modello più
grande per le risposte: vi dico perché quando arriviamo ai numeri.»

**1. Una domanda all'advisor, con la citazione** (8-14 secondi)

```bash
chiedi "$MARCO" "Quali controlli servono per un bonifico verso il Venezuela?"
```

Indica la riga `citati:`. In tutte e cinque le prove c'era `paesi_rischio_elevato`, il documento
interno che Marco può vedere. Indica anche i `[fonte-N]` nel testo.

**Cosa dici.** Mentre aspetti: «Marco chiede quali controlli servono per un bonifico verso il
Venezuela.» Quando arriva: «La risposta cita le sue fonti: qui l'elenco dei paesi a rischio, un
documento interno che Marco può vedere.»

**2. La stessa domanda, con il token di Giulia** (5-9 secondi)

```bash
chiedi "$GIULIA" "Quali controlli servono per un bonifico verso il Venezuela?"
```

In `citati:` compare `aml_controparti_venezuela`, il documento riservato della Compliance. È il
documento in più: a Marco non arriva mai, in nessuna delle cinque prove. Giulia lo ha citato in 4
prove su 5. Nella quinta non ha citato niente, ma il contenuto veniva comunque da lì: la verifica
rafforzata e la segnalazione dei bonifici sopra i 10.000 €.

**Cosa dici.** Mentre aspetti: «Ora la stessa domanda, con il token di Giulia, della
Compliance.» Quando arriva: «Fra le fonti c'è un documento in più: quello riservato sulle
controparti venezuelane, con la verifica rafforzata e la soglia dei 10.000 euro. A Marco non
arriva mai, perché il filtro sta nella ricerca, non nel prompt.»

**3. L'agente, con la traccia dei passi** (6-20 secondi)

```bash
agente "qual e il saldo del conto IT60X0542811101000000123?"
traccia
```

Indica tre cose:
- `passi: 2 | tool: ['get_account_balance'] | fermato da: model`;
- il saldo vero, 48.200,00 €;
- la riga della traccia: `passo 1 get_account_balance -> ok`.

Con `llama3.2:3b` è questa la forma che regge: un tool, poi la risposta. La catena di più tool
non regge, ed è il quarto punto di «cosa manca».

**Cosa dici.** Mentre aspetti: «Adesso l'agente: Marco chiede il saldo di un conto del suo
cliente.» Quando arriva: «Due passi: il modello ha scelto lo strumento del saldo, e ha risposto con
il dato vero, 48.200 euro.» Dopo `traccia`: «E questa è la traccia: ogni passo lascia una riga nel
log, con lo strumento e l'esito.»

**4. Una segnalazione sopra soglia che si ferma in attesa** (5-17 secondi)

```bash
agente "apri una segnalazione di compliance sul conto IT60X0542811101000000123: il cliente vuole fare un bonifico di 25.000 euro verso il Venezuela"
```

Indica `fermato da: awaiting_approval` e la frase «Nulla è stato ancora eseguito». La consegna
chiede di fermarsi qui. Se c'è tempo, mostra la ripresa (8-13 secondi):

```bash
in_attesa            # cosa vede Giulia: la pratica sospesa e chi l'ha chiesta
approva "$GIULIA"    # il run riprende: apri_segnalazione_compliance, e la segnalazione è aperta
traccia
```

Se dopo la firma di Giulia leggi `fermato da: awaiting_second_approval`, il modello non ha passato
l'importo nella chiamata al tool. Senza importo firmano in due: è l'estensione del Giorno 8. È
successo in 1 prova su 2. Allora firma anche Lucia: `approva "$LUCIA"`.

**Cosa dici.**
- Mentre aspetti: «L'ultima: Marco chiede di aprire una segnalazione sul bonifico da 25.000
  euro.»
- Quando arriva: «Il run si ferma prima di eseguire: sopra i 5.000 euro decide una persona. Non
  è stato eseguito niente: la pratica è salvata, e aspetta la firma di Giulia.»
- Se mostri la ripresa: «Giulia vede cosa sta approvando, e chi l'ha chiesto. Approva, e il run
  riprende da dove si era fermato: adesso la segnalazione è aperta.»
- Se servono due firme: «Il modello non ha passato l'importo, e senza importo il sistema chiede
  due firme: firma anche Lucia, che segue i rischi.»

**5. Per la difesa finale: la domanda a cui il sistema risponde che non sa** (3 secondi)

Lo showcase non la chiede, ma la consegna la vuole nella demo della difesa, ed è quella che
chiama «la più importante».

```bash
chiedi "$MARCO" "Che tempo fa domani a Milano?"
```

Indica «Non ho trovato informazioni sufficienti…» e `citati: []`.

**Cosa dici.** «E una domanda a cui il sistema non deve rispondere: che tempo fa domani a Milano.
Risponde che nei documenti non c'è, invece di inventare.»

### 4:00–4:40 — I tre numeri

**Cosa chiede il testo.** «I tre numeri: il recall@5 sul tuo insieme di casi, il p95 dell'advisor,
il costo medio per risposta. Sono la parte che ti distingue.»

**Già pronto.** I numeri e il loro metodo, dal README e dalla PR:

| Numero | Valore | Come l'ho misurato |
|---|---|---|
| recall@5 dell'advisor | 0,83: 25 domande su 30 | con il runner del Giorno 9, sul database del compose. Per ogni domanda di `evals/datasets/advice.jsonl` la riscrive, ne calcola l'embedding e recupera i 5 passaggi visibili al ruolo del caso. Il caso passa se fra i documenti recuperati c'è quello atteso. K=5 è il `top_k` di produzione |
| p95 dell'advisor | 9,1-9,9 s con la leva; 23,2 s prima | con `scripts.misura_tetti`, da fuori, come lo vive l'utente. Fa 60 domande: ogni domanda del dataset due volte, in un ordine mescolato sempre uguale, una alla volta, con Redis riavviato prima. Fra due misure di partenza il rumore è di 6,8 s |
| costo medio per risposta | 0 € | con lo stesso script. I modelli girano in locale su Ollama, e zero è il prezzo vero |

**Cosa dici** (105 parole, circa 40 secondi):

> Tre numeri, ciascuno con il comando che lo rifà. Recall a cinque: 0,83. Su trenta domande di
> prova, 25 trovano il documento giusto fra i cinque passaggi che quel ruolo può vedere; lo misura
> il runner degli eval. Tempo al 95° percentile dell'advisor, misurato da fuori su sessanta
> risposte: era 23 secondi, con un modello più piccolo per la risposta è sceso sotto i 10. Il
> prezzo: le risposte con la citazione sono passate da 15 su 30 a una, ed è per questo che la demo
> l'avete vista con il modello grande. Costo medio per risposta: zero euro, perché i modelli
> girano in locale.

La tabella sopra serve per la domanda che arriva di sicuro: «come lo hai misurato?».

**Per la difesa finale.** La consegna vuole i numeri «ottenuti lanciando il comando davanti a chi
guarda»:

```bash
DATABASE_URL=postgresql+asyncpg://lipari:lipari@127.0.0.1:5434/lipari_ai uv run python -m evals.runner   # 8-12 minuti
uv run python -m scripts.misura_tetti                                                                 # con la leva accesa
```

Usano tutti e due Ollama, quindi lanciali uno alla volta: insieme si rubano il tempo e falsano i
numeri.

### 4:40–5:00 — Cosa manca, e cosa faresti dopo

**Cosa chiede il testo.** «Cosa manca e cosa faresti dopo. Detto da te, prima che lo chiedano.»

**Già pronto.** I quattro punti della PR, in ordine di priorità:
1. **Un cancello sulla risposta.** Con la leva l'advisor cita in 1 risposta su 30 e sbaglia più
   cifre, e nessun cancello se ne accorge, perché i cancelli misurano il recupero.
2. **L'importo scritto all'italiana.** «19.300» viene letto come 19,30 €, e così la segnalazione
   salta l'approvazione: è il rilievo R4 della review L4.
3. **La coda di Ollama.** Serve una richiesta alla volta: trenta operatori il lunedì mattina
   farebbero minuti di coda.
4. **L'agente sulle domande a più passi.** Con `llama3.2:3b` usa un tool per domanda.

**Cosa dici** (52 parole, circa 20 secondi):

> Cosa manca, in ordine. Primo, un cancello sulla risposta: oggi misuro il recupero, e un modello
> che non cita passa lo stesso; i casi ci sono già, manca il misuratore. Secondo, un importo
> scritto 19.300 viene letto 19,30 euro, e salta l'approvazione. Poi la coda di Ollama, e l'agente
> a più passi.

## 5. Dopo lo showcase

```bash
docker compose up -d --no-deps api                 # la leva torna accesa, com'è consegnata
docker compose exec api printenv ADVICE_MODEL      # llama3.2:1b
```

## 6. Se qualcosa va storto in scena

| Cosa vedi | Cosa fai |
|---|---|
| `/ready` risponde 503 dopo un riavvio di Docker | `docker compose up -d` |
| un 401, o un errore sul token | il token è scaduto, dopo 30 minuti: incolla di nuovo il blocco del terminale |
| la prima risposta ci mette più di 30 secondi | è il modello a freddo: per questo c'è il riscaldamento |
| Giulia non cita | il contenuto viene comunque dal documento riservato: la verifica rafforzata, i 10.000 € |
| `awaiting_second_approval` | `approva "$LUCIA"` |

## 7. Le tre prove

«La demo si prova tre volte prima. Non perché possa rompersi — perché cinque minuti di parlato
con le mani su una tastiera richiedono di sapere a memoria quale comando viene dopo.»

| | Prova 1 | Prova 2 | Prova 3 |
|---|---|---|---|
| cinque minuti, con il cronometro | | | |
| le parti della demo, senza guardare il copione | | | |
| i tre numeri, con il metodo | | | |

## 8. Le dodici domande prevedibili

«Se una non ti torna in dieci secondi, la giornata corrispondente va ripresa stasera.»

| # | Domanda | Giornata da riprendere |
|---|---|---|
| 1 | Async: quando serve e quando non serve | G1 |
| 2 | Pydantic: cosa fa a runtime che un'interfaccia TypeScript non fa | G2 |
| 3 | SQLAlchemy: perché selectinload, e cos'è l'N+1 | G3 |
| 4 | RAG in cinque passi, e cosa il RAG non sa fare | G5 |
| 5 | Chunking: come scegli dimensione e sovrapposizione | G5 |
| 6 | Query rewriting: quale query va al retrieval e quale al modello | G6 |
| 7 | Retrieval per ruolo: dove metti il filtro, e perché non altrove | G6 |
| 8 | Tool use contro agente: la differenza strutturale | G4 e G7 |
| 9 | max_steps: guardrail o budget, e cosa restituisci quando lo raggiungi | G7 |
| 10 | Autorizzazione di un agente: perché non nel prompt | G7 |
| 11 | Eval contro test: cosa si misura e cosa si asserisce | G9 |
| 12 | Il costo: come lo modelli in un business case | G4, G7 e G9 |

## 9. I quattro anti-pattern del candidato

- «Ho usato un framework agentico», senza saper dire cosa fa il loop dentro. Il loop l'hai
  scritto tu: dillo.
- «Non ho mai fatto eval»: manca la cultura di ingegneria dell'AI, ed è il gap che si nota di più
  nel 2026.
- «Il RAG è una query sul database più un prompt»: mancano chunking, retrieval e citazione.
- «Il costo non lo conosco»: su un sistema che spende a ogni richiesta, è la risposta che chiude
  il colloquio.
