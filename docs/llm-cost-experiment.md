# Esperimento sul costo delle conversazioni

Misurazione del consumo di token dell'endpoint `/api/ai/chat` su dieci conversazioni da cinque turni, e proiezione della spesa che avrebbero avuto su un modello a pagamento.

## Come l'ho eseguito

Il corso non fornisce le chiavi di OpenAI e Anthropic, quindi ho servito il modello in locale con Ollama, che espone un endpoint compatibile con le API OpenAI. Ho aggiunto un terzo provider al layer di astrazione (`OllamaProvider`), cambiando solo `base_url`: il resto della catena — `ChatService`, la history, il salvataggio dei messaggi — è rimasto identico.

Questo significa che i **token sono misurati davvero**, mentre il **costo in euro è una proiezione**: in locale la spesa è zero, quindi ho applicato il listino di `gpt-4o-mini` ai token realmente consumati.

- Modello: `llama3.2:3b` servito da Ollama
- Endpoint: `POST /api/ai/chat`
- Dieci conversazioni, cinque turni ciascuna, cinquanta chiamate in tutto
- Stesse cinque domande in ogni conversazione, su temi bancari generici
- Durata complessiva: 837 secondi, circa quattordici minuti

## Risultati misurati

Query eseguita sul database al termine:

```sql
SELECT SUM(tokens), SUM(cost_eur), COUNT(*) FROM chat_messages
WHERE created_at > NOW() - INTERVAL '1 hour';
```

| | Valore |
|---|---|
| Token totali | 36 208 |
| Messaggi salvati | 100 (50 utente, 50 assistente) |
| Costo registrato | 0,00 euro (modello locale) |
| Media per conversazione | 3 621 token |
| Minimo / massimo | 3 336 / 3 852 token |

Il conteggio dei token è attribuito ai messaggi dell'assistente, perché è la risposta del modello a riportare l'uso complessivo della chiamata. I messaggi dell'utente risultano a zero.

## Costo proiettato su gpt-4o-mini

Listino usato, quello già presente in `src/llm/openai_provider.py`: 0,00014 euro per mille token in ingresso, 0,00056 in uscita.

Il database salva un solo totale per messaggio, quindi per separare input e output ho interrogato il modello chiedendo il dettaglio dell'uso su due chiamate campione, una a inizio conversazione e una a conversazione avanzata: 149 token di input contro 137 di output nella prima, 777 contro 80 nella seconda. Sull'insieme dei due campioni l'input pesa l'81% del totale, ed è la ripartizione che applico qui.

Applicando quella ripartizione ai 36 208 token misurati:

| | Token | Costo |
|---|---|---|
| Input | 29 329 | 0,00411 euro |
| Output | 6 879 | 0,00385 euro |
| **Totale** | **36 208** | **0,0080 euro** |

Da cui:

- **0,0008 euro per conversazione** da cinque turni
- **0,00016 euro per turno**

Vale la pena notare che input e output contribuiscono quasi in parti uguali alla spesa, pur essendo l'input l'81% dei token: l'output costa quattro volte tanto al token, e questo compensa.

## Cosa significa su volumi reali

| Conversazioni al giorno | Costo al giorno | Costo al mese |
|---|---|---|
| 100 | 0,08 euro | 2,40 euro |
| 1 000 | 0,80 euro | 24 euro |
| 10 000 | 7,96 euro | 239 euro |

Il tetto giornaliero configurato in `MAX_EUR_PER_DAY` è 5 euro, che a questi numeri corrisponde a circa 6 250 conversazioni al giorno prima che il guardrail cominci a rispondere 429.

## Limiti di questa misurazione

I token sono stati contati su `llama3.2:3b`, non su `gpt-4o-mini`. Modelli diversi hanno tokenizzatori diversi, e soprattutto sono più o meno prolissi: un modello che risponde più lungo consuma più output, che è la parte cara. La proiezione va letta come un ordine di grandezza, non come una previsione di fattura.

La ripartizione fra input e output è stimata su due campioni, primo e quinto turno, non sull'intero esperimento: il database salva solo il totale per messaggio. Per avere il dato esatto andrebbero aggiunte due colonne, `input_tokens` e `output_tokens`, al modello `ChatMessage`.

Le conversazioni in streaming, infine, salvano token e costo a zero, perché i chunk dell'SSE non portano il conteggio dell'uso. Non incidono su questo esperimento, che è passato tutto da `/api/ai/chat`, ma restano invisibili al cost guardrail: è un difetto noto, non una dimenticanza.
