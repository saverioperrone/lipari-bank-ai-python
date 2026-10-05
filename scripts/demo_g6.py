"""La demo di due minuti: la stessa domanda fatta da due ruoli, una sotto l'altra.

    uv run python -m scripts.demo_g6
    uv run python -m scripts.demo_g6 "ven ok?"

Passa dall'API come un client vero, quindi il server deve essere acceso. Per ognuno dei
due utenti stampa la domanda riscritta, le fonti citate e la risposta: la riscrittura e'
la stessa, le fonti no, perche' Giulia vede il documento riservato e Marco no.

Due avvertenze da dire in demo. Le fonti sono quelle che il modello cita con [fonte-N],
e il modello locale le scrive circa una volta su due: se escono vuote, si rilancia. La
prima risposta dopo l'avvio del server puo' superare il timeout e uscire come risposta
parziale: conviene lanciare la demo una volta prima, a vuoto.
"""

import asyncio
import sys

import httpx

API = "http://localhost:8000"
DOMANDA = "Cosa si deve fare con un bonifico verso una controparte in Venezuela?"
UTENTI = (("mbianchi", "Marco Bianchi, operator"), ("grossi", "Giulia Rossi, compliance_lead"))


async def main() -> None:
    domanda = sys.argv[1] if len(sys.argv) > 1 else DOMANDA
    print(f"domanda: {domanda}\n")
    async with httpx.AsyncClient(timeout=120.0) as client:
        for username, chi in UTENTI:
            login = await client.post(
                f"{API}/api/auth/login", data={"username": username, "password": "bootcamp"}
            )
            login.raise_for_status()
            token = login.json()["access_token"]
            risposta = await client.post(
                f"{API}/api/ai/advice",
                json={"question": domanda},
                headers={"Authorization": f"Bearer {token}"},
            )
            risposta.raise_for_status()
            dati = risposta.json()
            fonti = [c["document_id"] for c in dati["citations"]]
            print(f"=== {chi}")
            print(f"cercata:  {dati['rewritten_query']}")
            print(f"fonti:    {fonti or 'nessuna citazione'}")
            print(f"risposta: {dati['answer']}\n")


if __name__ == "__main__":
    asyncio.run(main())
