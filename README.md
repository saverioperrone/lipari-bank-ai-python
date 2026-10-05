# LipariBank AI

Bootcamp Python AI v2 — Lipari Consulting.

FastAPI backend with Pydantic Settings config, managed with uv.

## Requirements

- Python 3.12+
- uv (package manager)

## Setup

```bash
uv sync
cp .env.example .env   # then fill in real values (DB, API keys, JWT secret)
```

`uv sync` creates the virtual environment and installs all dependencies (including dev tools) from `uv.lock`.

## Run

```bash
uv run uvicorn src.main:app --reload
```

- App: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs

## Development

```bash
uv run ruff check src      # lint
uv run ruff format src     # format
uv run mypy src            # type check (strict)
uv run pytest              # tests
```

## Project structure

```
src/
├── config.py               # Pydantic Settings, loaded from .env
├── main.py                 # FastAPI app, middleware, exception handler, router registration
├── exceptions.py            # AppError e sottoclassi di dominio
├── api/
│   ├── auth.py              # POST /api/auth/login (G6)
│   ├── chat.py              # POST /api/ai/chat (echo)
│   ├── categorize.py        # POST /api/ai/categorize (dummy by keyword)
│   └── advice.py            # POST /api/ai/advice e /api/ai/documents/ingest (G5)
├── auth/                    # G6
│   ├── tokens.py            # emissione e verifica dei JWT
│   ├── deps.py              # get_current_user, require_role
│   ├── passwords.py         # hash argon2
│   └── acl.py               # la matrice ruolo → livelli di visibilità
├── types/
│   ├── chat.py               # ChatRequest, ToolCallInfo, ChatResponse
│   ├── categorize.py         # CategorizeRequest, CategorizeResponse
│   ├── advice.py             # AdviceRequest, AdviceResponse, Citation, Ingest*
│   └── error.py              # ErrorResponse
└── lipari_bank_ai/
    └── __init__.py         # installable package entry point
```

## API

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/auth/login` | Login con form OAuth2: restituisce un access token JWT di 30 minuti (G6) |
| POST | `/api/ai/chat` | Chat AI, a nome dell'utente del token (G6) |
| POST | `/api/ai/categorize` | Categorizzazione transazione — dummy by keyword (LLM reale in G4) |
| POST | `/api/ai/advice` | Risposta vincolata ai documenti, con le fonti citate; token obbligatorio, 15 richieste al minuto per utente (G6) |
| POST | `/api/ai/documents/ingest` | Carica un documento nell'indice (sostituisce se l'id esiste); solo `compliance_lead` e `admin` (G6) |

Tutti gli errori (custom `AppError`, validazione Pydantic, eccezioni impreviste) tornano nello stesso formato JSON: `timestamp`, `status`, `error`, `message`, `path` (+ `details` per la validazione). Fanno eccezione i 401 e i 403 dell'autenticazione, che escono come `{"detail": ...}`: è il rilievo non corretto di `docs/ai-review/G6.md`. Ogni response include l'header `X-Request-Id`.

## Giorno 5 — RAG con citazioni

Lo sportello risponde solo su quello che c'e' scritto nelle circolari di LipariBank, dice
da quale passaggio viene ogni affermazione, e quando la risposta non c'e' lo dice.

### Farlo girare

```bash
docker compose up -d                       # Postgres con pgvector, e Ollama
docker exec ollama ollama pull llama3.2:3b
docker exec ollama ollama pull nomic-embed-text
uv run alembic upgrade head
uv run uvicorn src.main:app --reload       # in un altro terminale
uv run python -m scripts.ingest_docs       # carica le quattro circolari di data/docs/
uv run python -m scripts.eval_retrieval --etichetta baseline           # solo vettoriale
uv run python -m scripts.eval_retrieval --etichetta ibrida --ibrida    # con la lessicale
uv run python -m scripts.eval_retrieval --etichetta deduplica --dedup  # il controllo
uv run pytest
```

### La demo di due minuti

Una domanda con la sua citazione:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ai/advice -H "content-type: application/json" -d '{"question": "Per quanti anni vanno conservati i documenti della adeguata verifica?"}'
```

> I documenti della adeguata verifica vanno conservati per **10 anni** dalla cessazione
> del rapporto o dall'esecuzione dell'operazione occasionale. [fonte-1]
>
> `circolare-09-obblighi-segnalazione`, paragrafo 5 — si apre il file e la frase c'e'.

Anche il marcatore, come il rifiuto qui sotto, non e' garantito: a volte il modello cita
a parole — «secondo la circolare 09/2026» — e in quel caso la risposta e' giusta ma
`citations` torna vuoto, perche' le citazioni si estraggono dai marcatori. Se succede in
demo, si rilancia: e' la stessa variabilita' del rifiuto, e va detta invece che nascosta.

Una domanda a cui il sistema risponde che non sa:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ai/advice -H "content-type: application/json" -d '{"question": "Quanto costa affittare una cassetta di sicurezza per un anno?"}'
```

> Non ho trovato informazioni sufficienti nei documenti disponibili.
>
> citazioni: 0

Da dire ad alta voce: **il rifiuto non e' garantito.** Su nove tentativi con una domanda
di questo tipo, sei rifiutano e tre inventano un numero. Lo decide il modello, non il
codice.

Il terzo pezzo della demo e' il numero prima e dopo, nella tabella qui sotto.

### L'estensione scelta: ricerca lessicale affiancata alla vettoriale

Alla ricerca vettoriale si affianca la ricerca a parole di Postgres (`tsvector`, indice
GIN, colonna generata da `content`), e i due elenchi si fondono per **rango** e non per
punteggio: una similarita' coseno e un `ts_rank_cd` stanno su scale diverse, e sommarli
vuol dire decidere a caso quanto pesa una delle due ricerche.

**Tre righe a difesa del disegno.** Ho scelto la ricerca ibrida perche' il recupero
sbagliava due domande su dieci portando documenti che la domanda non nominava, e le
parole mancanti erano scritte nel passaggio giusto. Ho scartato di lasciare che la
ricerca lessicale *introduca* passaggi che il vettore non aveva trovato: alzava il
recupero a 10/10 ma rompeva il rifiuto — su una domanda la cui risposta non sta in
nessun documento, tre tentativi su tre rifiutavano col solo vettore e **zero su tre**
con la fusione aperta, perche' il lessicale trova sempre qualcosa e cinque passaggi in
tema bastano al modello per inventare un numero. La lessicale quindi riordina i
candidati del vettore e non ne aggiunge, e il numero per cui lo so e' 10/10 di recupero
con il rifiuto tornato a 6 volte su 9.

### La misura

Dieci domande di cui si sa in quale documento sta la risposta (`scripts/domande.py`),
scritte con le parole di chi chiede e non con quelle della circolare.

| | hit@5 | hit@1 |
|---|---|---|
| solo vettoriale (linea di partenza) | 8/10 | 7/10 |
| vettoriale + deduplica, controllo | 8/10 | 7/10 |
| **ibrida, dopo l'estensione** | **10/10** | 7/10 |

Il delta e' **+2 su hit@5**, e la riga di controllo serve a dire da dove viene: la sola
deduplica dei passaggi ripetuti non sposta niente, quindi i due punti sono della ricerca
lessicale. `hit@1` non si muove: la fusione porta dentro il documento giusto, non lo
mette primo.

Le misure stanno in `docs/eval/*.json`, i rilievi sul codice in `docs/ai-review/G5.md`.

### Le quattro prove del cancello

| Prova | Esito |
|---|---|
| Domanda plausibile ma estranea al corpus | rifiuto, zero citazioni — ma 6 volte su 9, non sempre |
| Stesso documento caricato due volte | 11 passaggi prima e dopo, una citazione |
| Documento con una pagina ripetuta | una citazione, non due identiche |
| Domanda vaga di due parole | rifiuto |

La prima prova non e' deterministica: il modello locale gira a `temperature=0.3` e il
rifiuto resta una scelta sua, non un controllo del codice.

## Giorno 6 — Chi chiede, e cosa può vedere

Da oggi l'advisor sa chi sta chiedendo: login con token JWT, una matrice ruolo → livelli
di visibilità, e il filtro dei permessi dentro il `WHERE` della ricerca. Davanti al
recupero c'è un riscrittore che trasforma le domande da sportello in domande che la
ricerca sa usare, e la riscritta torna nella risposta (`rewritten_query`): chi legge ha
il diritto di sapere cosa è stato cercato al posto suo.

### Farlo girare

```bash
docker compose up -d                        # Postgres con pgvector, e Ollama
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_users         # Marco, Giulia, Lucia: password «bootcamp»
uv run uvicorn src.main:app --reload        # in un altro terminale
uv run python -m scripts.ingest_docs        # login di Giulia, poi le circolari con il loro livello
uv run python -m scripts.demo_g6            # la stessa domanda da Marco e da Giulia
```

Il livello di visibilità di un documento è la sua sottocartella:
`data/docs/compliance_only/aml_controparti_venezuela.md` è il documento riservato del
canarino, le circolari lasciate in `data/docs/` sono pubbliche.

| Utente | Ruolo | Vede |
|---|---|---|
| `mbianchi` | operator | public, internal |
| `grossi` | compliance_lead | public, internal, compliance_only |
| `lverdi` | risk_lead | public, internal, risk_only |

```bash
curl -s -X POST localhost:8000/api/auth/login -d "username=mbianchi&password=bootcamp"
# {"access_token":"eyJ...","token_type":"bearer"} — nel payload, in chiaro, solo sub, role, iat ed exp
```

### Le prove del cancello

Sul mio indice, con i miei token, la stessa domanda per tutti: «Cosa si deve fare con un
bonifico verso una controparte in Venezuela?». La frase riservata si riconosce da quattro
parole che stanno solo nel documento del canarino: «10.000», «sospeso», «istruttorie»,
«EDD».

| Prova | Esito |
|---|---|
| Il token di Marco | la frase riservata non compare, né nella risposta né nelle fonti |
| Il token di Giulia | compare in 3 tentativi su 3, e in 2 su 3 il documento riservato è anche fra le fonti |
| Token alterato di un carattere | 401 «Token non valido» |
| Token scaduto | 401 «Token scaduto»: distinto dal precedente, chi lo riceve sa che deve rifare il login |
| Ruolo inesistente nel token («stagista») | solo fonti pubbliche, e nel log del server `ruolo_sconosciuto` |
| Nessun token | 401 |

Le stesse proprietà le provano i test del blueprint (`tests/test_g6.py`), con un modello
finto che le citazioni le scrive sempre.

### La misura: le dieci domande con il riscrittore davanti

| | hit@5 | hit@1 |
|---|---|---|
| solo vettoriale, ieri e oggi: la ricerca di `/advice` da oggi | 8/10 | 7/10 |
| **vettoriale con il riscrittore v2 davanti** | **9/10** | 6/10 |

```bash
uv run python -m scripts.eval_retrieval --etichetta vettoriale_g6
uv run python -m scripts.eval_retrieval --etichetta riscrittore --riscrittore
```

Il delta è **+1 su hit@5 e −1 su hit@1**, ed è la linea di partenza. Il punto guadagnato
è la domanda sui documenti dell'identificazione, che riscritta trova la circolare 09. Un
altro «OK» è fortunato: «Mi hanno rubato la carta…» viene riscritta come la copia di un
esempio del prompt, e la circolare giusta entra fra le cinque lo stesso. La ricerca
ibrida del Giorno 5 (10/10) resta negli script di misura: `/advice` usa
`search_for_user`, l'unica ricerca con il filtro dei permessi.

### L'estensione C: la riscrittura che non si ripaga due volte

La cache esisteva già (`rewrite_cached`): l'estensione decide la chiave e la misura. La
chiave è il prompt più la domanda normalizzata (minuscole, spazi singoli, senza la
punteggiatura finale), il deposito si può passare da fuori, e `cache_hit` finisce nella
riga di log `advice_completata`.

```bash
uv run python -m scripts.misura_cache              # la misura: trenta richieste
uv run pytest tests/test_cache_riscrittura.py      # il test della proprietà
uv run mypy src scripts                            # strict
```

| Trenta richieste: dieci domande ellittiche, ognuna tre volte | |
|---|---|
| servite dalla cache, con la chiave normalizzata | 20 |
| servite con la chiave grezza, la domanda così com'è | 10 |
| chiamate al modello | 10 invece di 30 |
| una riscrittura vera / una dalla cache | 1,9 s / 0,01 ms |
| tempo totale | 18,7 s invece di ~56 |
| lo stesso deposito con il prompt v1 | torna al modello, come deve |

La sequenza è costruita, non presa da un log: ogni domanda due volte identica e una con
maiuscole, spazi o punteggiatura diversi. Misura quanto vale la chiave, non quanto si
ripetono le domande in filiale.

**Tre righe a difesa del disegno.** Ho scelto come chiave il prompt più la domanda
normalizzata, perché sulle trenta richieste la cache ne serve 20 invece delle 10 della
chiave grezza, e le chiamate al modello scendono da 30 a 10. Ho scartato la chiave sulla
sola domanda, che è quella della teoria: con un deposito condiviso un prompt nuovo
riceverebbe le riscritture del vecchio, ed è quello che il test dell'estensione verifica
che non succeda. Il prezzo è la trappola della consegna: la cache congela anche le
riscritture sbagliate di un modello non deterministico — «entro quando?» diventa una
domanda sul Venezuela e resta così finché il processo vive — e l'unica difesa è non
salvare i ripieghi.

### La demo di due minuti

```bash
uv run python -m scripts.demo_g6                   # la domanda del canarino
uv run python -m scripts.demo_g6 "ven ok?"         # la domanda del blueprint
```

Stessa domanda, stessa riscrittura, fonti diverse: Marco ha la circolare 17, Giulia ha in
testa `aml_controparti_venezuela`. Da dire ad alta voce: le fonti sono i `[fonte-N]` che
il modello scrive, e il modello locale li scrive circa una volta su due; se escono vuote,
si rilancia. La prima risposta dopo l'avvio del server può superare il timeout di 30
secondi e uscire come risposta parziale: la demo si lancia una volta prima, a vuoto.

### I test

```bash
uv run pytest     # i 13 del blueprint adattati, quello dell'estensione, quello del Giorno 5
```

⚠️ La fixture del blueprint fa `TRUNCATE` di `document_chunks`, `chat_sessions` e
`chat_messages` sul database del `.env`: dopo `pytest` l'indice e le chat sono vuoti. Si
salva lo stato prima e si ripristina dopo:

```bash
docker compose exec -T postgres pg_dump -U lipari -d lipari_ai --data-only -t document_chunks -t chat_sessions -t chat_messages > backup.sql
uv run pytest
docker compose exec -T postgres psql -U lipari -d lipari_ai -c "TRUNCATE document_chunks, chat_messages, chat_sessions CASCADE"
docker compose exec -T postgres psql -U lipari -d lipari_ai < backup.sql
```

Oppure si rilancia `scripts.ingest_docs`, che però rifà solo l'indice, non le chat.

### Cosa resta da sapere

- Le citazioni di `/advice` escono circa una volta su due: il prompt v2 (prompting clinic,
  esercizio 3) le ha portate da 0 su 6 a 5 su 9, ma il marcatore lo scrive il modello.
- Il riscrittore copia gli esempi del prompt quando la domanda rimanda a una precedente:
  `/advice` non riceve la storia della conversazione.
- Un documento con un'istruzione nascosta non fa uscire niente di riservato, ma la frase
  finisce nella risposta (prompting clinic, esercizio 4).

I rilievi sul codice stanno in `docs/ai-review/G6.md`, gli esercizi sui prompt in
`docs/prompting-clinic/G6.md`, i tre prompt di vibe coding in `docs/vibe-coding/G6.md`. Le
misure grezze stanno in `docs/eval/*.json`.

## Decisione di design — response_model esplicito vs return type hint

Sui due endpoint di oggi uso `response_model` esplicito (`response_model=ChatResponse`, `response_model=CategorizeResponse`) invece di fidarmi solo del return type hint. Il return type hint lo legge mypy in fase di sviluppo ma non viene eseguito a runtime; `response_model` invece valida e filtra davvero l'output ad ogni richiesta, anche se il service dovesse un giorno restituire per errore un campo in più (es. un id interno). Su endpoint pubblici preferisco il controllo più rigido a runtime, anche a costo di qualche riga in più nel decoratore.

## Difetti trovati nello starter di Gino

Confrontando `starter-collega/` con il codice di riferimento del progetto:

- **`AppException` invece di `AppError`** (`src/exceptions.py`): nome della classe base diverso da quello richiesto/insegnato. Corretto rinominando classe base e sottoclassi.
- **`class Config` in `ChatResponse`** (`src/types/chat.py`): sintassi Pydantic v1 per l'esempio Swagger — in v2 viene ignorata in silenzio, quindi non produce alcun effetto. Rimossa.
- **`response_model` mancante su `/api/ai/chat`** (`src/api/chat.py`): l'endpoint non dichiarava `response_model=ChatResponse`, quindi né la validazione dell'output né lo schema in `/docs` erano garantiti. Aggiunto.
- **Handler generico che espone l'errore e risponde 200** (`src/main.py`): `general_exception_handler` faceva `JSONResponse(content={"error": str(exc)})` senza `status_code` esplicito (default 200) e con il messaggio d'errore reale esposto al client. Corretto con `status_code=500` esplicito e messaggio generico — nessuno stack trace in risposta.
