#!/usr/bin/env bash
# scripts/smoke.sh — il sistema, non i servizi: sette prove che attraversano dieci giornate.
# Si lancia dopo `docker compose up`, e tre minuti prima dello showcase.
set -euo pipefail
BASE=${BASE:-http://localhost:8000}
ok() { printf '  ok  %s\n' "$1"; }
no() { printf '  NO  %s\n' "$1"; exit 1; }
campo() { python -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
token() {
  curl -sf -X POST "$BASE/api/auth/login" -d "username=$1&password=bootcamp" | campo "d['access_token']"
}

# 0. le due sonde: vivo e pronto
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health")" = 200 ] && ok "vivo" || no "vivo"
[ "$(curl -s "$BASE/ready" | campo "d['status']")" = ready ] && ok "pronto" || no "pronto"

# 1. Marco, Giulia e Lucia entrano (il login del Giorno 6)
TOK_M=$(token mbianchi); TOK_G=$(token grossi); TOK_L=$(token lverdi)
ok "login di tre ruoli"

# 2. Marco chiede come chiede davvero: risposta, citazione, riscrittura (Giorni 5 e 6). Una
#    domanda informale che llama3.2:3b cita: a «ven ok?» risponde con il rifiuto, senza fonti
DOMANDA='{"question":"bonifico extra sepa tempi"}'
ADV_M=$(curl -sf -X POST "$BASE/api/ai/advice" -H "Authorization: Bearer $TOK_M" \
  -H "Content-Type: application/json" -d "$DOMANDA")
[ "$(echo "$ADV_M" | campo "len(d['citations']) > 0 and bool(d['rewritten_query'])")" = True ] \
  && ok "advice di Marco: citazione e riscrittura" || no "advice di Marco"

# 3. una domanda la cui risposta sta solo nel documento riservato (l'ACL del Giorno 6):
#    Giulia lo cita, Marco no. Sulla stessa domanda generica, l'ordine dei passaggi potrebbe
#    far citare a entrambi il documento pubblico, e la prova non direbbe niente
RISERVATA='{"question":"Cosa non si comunica al cliente sulle istruttorie in corso?"}'
citati() {
  curl -sf -X POST "$BASE/api/ai/advice" -H "Authorization: Bearer $1" \
    -H "Content-Type: application/json" -d "$RISERVATA" | campo "sorted({c['document_id'] for c in d['citations']})"
}
DOC_G=$(citati "$TOK_G"); DOC_M=$(citati "$TOK_M")
case "$DOC_G" in *aml_controparti_venezuela*) ok "Giulia vede l'istruttoria" ;; *) no "Giulia: $DOC_G" ;; esac
case "$DOC_M" in *aml_controparti_venezuela*) no "Marco vede l'istruttoria" ;; *) ok "Marco no" ;; esac

# 4. l'agente fa più di un passo, su un conto del portafoglio di Marco (Giorno 7). La domanda
#    porta l'IBAN, come nella demo del Giorno 7: llama3.2:3b usa un tool per domanda, e con il
#    solo codice cliente passa il codice al posto dell'IBAN
RUN=$(curl -sf -X POST "$BASE/api/ai/agent" -H "Authorization: Bearer $TOK_M" \
  -H "Content-Type: application/json" \
  -d '{"message":"qual e il saldo del conto IT60X0542811101000000123?"}')
[ "$(echo "$RUN" | campo "d['steps'] >= 2 and 'get_account_balance' in d['tool_calls'] and d['stopped_by'] == 'model'")" = True ] \
  && ok "agente: $(echo "$RUN" | campo "','.join(d['tool_calls'])")" || no "agente: $RUN"

# 5. la stessa domanda, la seconda volta: la riscrittura arriva dalla cache (Giorno 10)
curl -sf -X POST "$BASE/api/ai/advice" -H "Authorization: Bearer $TOK_M" \
  -H "Content-Type: application/json" -d "$DOMANDA" > /dev/null
${COMPOSE:-docker compose} logs api --since 1m 2>/dev/null | grep -q '"cache_hit": true' \
  && ok "riscrittura dalla cache" || no "nessun cache_hit nei log"

# 6. il registro c'è, e Marco non lo vede (Giorno 9). Con Ollama il costo è zero: si contano
#    le chiamate registrate, non gli euro
DAL=$(date -u +%Y-%m-%d)  # il giorno del rapporto è UTC, come created_at
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/admin/cost-report?dal=$DAL" \
  -H "Authorization: Bearer $TOK_M")" = 403 ] && ok "Marco non vede i costi" || no "Marco vede i costi"
[ "$(curl -sf "$BASE/api/admin/cost-report?dal=$DAL" -H "Authorization: Bearer $TOK_L" \
  | campo "sum(v['chiamate'] for v in d['per_endpoint']) > 0")" = True ] && ok "Lucia vede i costi" || no "rapporto di Lucia"

echo "smoke: tutto a posto"
