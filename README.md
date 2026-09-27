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
│   ├── chat.py              # POST /api/ai/chat (echo)
│   ├── categorize.py        # POST /api/ai/categorize (dummy by keyword)
│   └── advice.py            # POST /api/ai/advice e /api/ai/documents/ingest (G5)
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
| POST | `/api/ai/chat` | Chat AI — echo (LLM reale in G4) |
| POST | `/api/ai/categorize` | Categorizzazione transazione — dummy by keyword (LLM reale in G4) |
| POST | `/api/ai/advice` | Risposta vincolata ai documenti, con le fonti citate |
| POST | `/api/ai/documents/ingest` | Carica un documento nell'indice (sostituisce se l'id esiste) |

Tutti gli errori (custom `AppError`, validazione Pydantic, eccezioni impreviste) tornano nello stesso formato JSON: `timestamp`, `status`, `error`, `message`, `path` (+ `details` per la validazione). Ogni response include l'header `X-Request-Id`.

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
uv run python -m scripts.ingest_corpus     # carica le quattro circolari di corpus/
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

## Decisione di design — response_model esplicito vs return type hint

Sui due endpoint di oggi uso `response_model` esplicito (`response_model=ChatResponse`, `response_model=CategorizeResponse`) invece di fidarmi solo del return type hint. Il return type hint lo legge mypy in fase di sviluppo ma non viene eseguito a runtime; `response_model` invece valida e filtra davvero l'output ad ogni richiesta, anche se il service dovesse un giorno restituire per errore un campo in più (es. un id interno). Su endpoint pubblici preferisco il controllo più rigido a runtime, anche a costo di qualche riga in più nel decoratore.

## Difetti trovati nello starter di Gino

Confrontando `starter-collega/` con il codice di riferimento del progetto:

- **`AppException` invece di `AppError`** (`src/exceptions.py`): nome della classe base diverso da quello richiesto/insegnato. Corretto rinominando classe base e sottoclassi.
- **`class Config` in `ChatResponse`** (`src/types/chat.py`): sintassi Pydantic v1 per l'esempio Swagger — in v2 viene ignorata in silenzio, quindi non produce alcun effetto. Rimossa.
- **`response_model` mancante su `/api/ai/chat`** (`src/api/chat.py`): l'endpoint non dichiarava `response_model=ChatResponse`, quindi né la validazione dell'output né lo schema in `/docs` erano garantiti. Aggiunto.
- **Handler generico che espone l'errore e risponde 200** (`src/main.py`): `general_exception_handler` faceva `JSONResponse(content={"error": str(exc)})` senza `status_code` esplicito (default 200) e con il messaggio d'errore reale esposto al client. Corretto con `status_code=500` esplicito e messaggio generico — nessuno stack trace in risposta.
