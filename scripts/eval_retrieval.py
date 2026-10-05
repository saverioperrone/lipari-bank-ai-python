"""La misura: quante volte il recupero porta il documento giusto fra i primi cinque.

    uv run python -m scripts.eval_retrieval --etichetta baseline
    uv run python -m scripts.eval_retrieval --etichetta ibrida --ibrida
    uv run python -m scripts.eval_retrieval --etichetta riscrittore --riscrittore

Chiama il recupero, non `/advice`: il numero da misurare e' del retrieval, e passare
dalla generazione ci metterebbe dentro la latenza del modello e la sua variabilita'
senza aggiungere niente alla domanda "il documento giusto e' arrivato?".

Le dieci domande sono scritte con le parole di chi chiede, non con quelle della
circolare: se ricalcassero il testo il recupero verrebbe dieci su dieci e la misura non
direbbe niente. Restano fisse fra la misura di partenza e quella dopo l'estensione,
altrimenti il delta non e' un delta.
"""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from src.db.session import AsyncSessionLocal
from src.lib.dedup import senza_ripetizioni
from src.llm.embedding_client import EmbeddingClient
from src.llm.factory import build_llm_provider
from src.llm.prompt import load_prompt
from src.llm.rewriter import QueryRewriter
from src.services.retrieval_service import SOGLIA_PREDEFINITA, RetrievalService

USCITA = Path(__file__).parent.parent / "docs" / "eval"
PRIMI = 5   # quanti passaggi finiscono nel contesto, come in RAGService


class Domanda(BaseModel):
    testo: str
    atteso: str      # il document_id che contiene la risposta
    nota: str        # dove sta, per poter rifare la verifica a mano


DOMANDE: list[Domanda] = [
    Domanda(
        testo="Quanto posso mandare al massimo in un giorno all'estero dal sito della banca?",
        atteso="circolare-17-bonifici-estero",
        nota="par. 2 — 15.000 euro al giorno da home banking",
    ),
    Domanda(
        testo="Da quale cifra scatta il controllo rafforzato"
              " se il destinatario sta in un paese rischioso?",
        atteso="circolare-17-bonifici-estero",
        nota="par. 5 — oltre 7.500 euro",
    ),
    Domanda(
        testo="In quanti giorni arrivano i soldi a chi li riceve fuori dall'Europa?",
        atteso="circolare-17-bonifici-estero",
        nota="par. 4 — terzo giorno lavorativo, quinto in divisa diversa dall'euro",
    ),
    Domanda(
        testo="Entro quanto devo annotare un versamento in contanti importante?",
        atteso="circolare-09-obblighi-segnalazione",
        nota="par. 2 — 30 giorni nell'Archivio Unico Informatico",
    ),
    Domanda(
        testo="Chi decide se mandare la segnalazione all'autorita'?",
        atteso="circolare-09-obblighi-segnalazione",
        nota="par. 4 — il Delegato antiriciclaggio, in via esclusiva",
    ),
    Domanda(
        testo="Per quanti anni vanno tenuti i documenti raccolti quando si identifica un cliente?",
        atteso="circolare-09-obblighi-segnalazione",
        nota="par. 5 — 10 anni",
    ),
    Domanda(
        testo="Dopo quanto tempo un cliente ha diritto allo sconto sulle spese del conto?",
        atteso="circolare-22-clienti-storici",
        nota="par. 1 e 2 — 96 mesi, riduzione del 40 per cento",
    ),
    Domanda(
        testo="Quando si perdono le condizioni riservate a chi e' cliente da tanti anni?",
        atteso="circolare-22-clienti-storici",
        nota="par. 5 — 18 mesi senza movimenti, sofferenza, revoca, recesso",
    ),
    Domanda(
        testo="Quanti soldi posso tenere su una ricaricabile normale?",
        atteso="circolare-31-carte-prepagate",
        nota="par. 3 — 2.500 euro sulla carta base",
    ),
    Domanda(
        testo="Mi hanno rubato la carta, cosa devo fare dopo averla bloccata?",
        atteso="circolare-31-carte-prepagate",
        nota="par. 4 — denuncia entro 48 ore e consegna in filiale",
    ),
]


class Esito(BaseModel):
    domanda: str
    cercata: str     # quello che e' arrivato al recupero: la domanda, o la sua riscritta
    atteso: str
    recuperati: list[str]
    hit_k: bool
    hit_1: bool
    vuoto: bool
    similarita_massima: float


class Misura(BaseModel):
    etichetta: str
    quando: str
    top_k: int
    soglia: float
    ricerca: str
    hit_at_k: int
    hit_at_1: int
    vuoti: int
    totale: int
    dettaglio: list[Esito]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--etichetta", default="baseline", help="nome della misura")
    parser.add_argument(
        "--ibrida", action="store_true", help="affianca la ricerca lessicale e fonde i ranghi"
    )
    parser.add_argument(
        "--dedup",
        action="store_true",
        help="solo vettoriale, ma scartando i passaggi ripetuti: serve a separare"
        " quanto del guadagno viene dalla deduplica e quanto dalla ricerca lessicale",
    )
    parser.add_argument(
        "--riscrittore",
        action="store_true",
        help="riscrive la domanda prima di cercare, come fa /advice dal Giorno 6",
    )
    args = parser.parse_args()

    # lo stesso riscrittore dell'app: prompt v2, temperatura 0
    riscrittore = (
        QueryRewriter(build_llm_provider(temperature=0), load_prompt("rewrite_system_v2"))
        if args.riscrittore
        else None
    )

    embedder = EmbeddingClient()
    esiti: list[Esito] = []

    async with AsyncSessionLocal() as session:
        retrieval = RetrievalService(session)
        for d in DOMANDE:
            cercata = await riscrittore.rewrite(d.testo) if riscrittore else d.testo
            vettore = await embedder.embed_one(cercata)
            if args.ibrida:
                passaggi = await retrieval.search_ibrida(
                    cercata, vettore, top_k=PRIMI, soglia=SOGLIA_PREDEFINITA
                )
            elif args.dedup:
                candidati = await retrieval.search(
                    vettore, top_k=PRIMI * 3, soglia=SOGLIA_PREDEFINITA
                )
                passaggi = senza_ripetizioni(candidati, PRIMI, testo=lambda p: p.content)
            else:
                passaggi = await retrieval.search(vettore, top_k=PRIMI, soglia=SOGLIA_PREDEFINITA)
            documenti = [p.document_id for p in passaggi]
            esiti.append(
                Esito(
                    domanda=d.testo,
                    cercata=cercata,
                    atteso=d.atteso,
                    recuperati=documenti,
                    hit_k=d.atteso in documenti,
                    hit_1=bool(documenti) and documenti[0] == d.atteso,
                    vuoto=not documenti,
                    similarita_massima=passaggi[0].similarity if passaggi else 0.0,
                )
            )

    misura = Misura(
        etichetta=args.etichetta,
        quando=datetime.now(UTC).isoformat(),
        top_k=PRIMI,
        soglia=SOGLIA_PREDEFINITA,
        ricerca=(
            'ibrida' if args.ibrida else 'vettoriale + deduplica' if args.dedup
            else 'solo vettoriale'
        ) + (' + riscrittore' if args.riscrittore else ''),
        hit_at_k=sum(1 for e in esiti if e.hit_k),
        hit_at_1=sum(1 for e in esiti if e.hit_1),
        vuoti=sum(1 for e in esiti if e.vuoto),
        totale=len(esiti),
        dettaglio=esiti,
    )

    print(f"\nmisura: {misura.etichetta}   top_k={misura.top_k}   soglia={misura.soglia}\n")
    for e in esiti:
        segno = "OK " if e.hit_k else "NO "
        primo = " (primo)" if e.hit_1 else ""
        print(f"{segno}{e.domanda[:62]:64} sim {e.similarita_massima:.3f}{primo}")
        if e.cercata != e.domanda:
            print(f"    cercata: {e.cercata}")
        if not e.hit_k:
            print(f"    atteso {e.atteso}, recuperato {e.recuperati or 'niente'}")
    print(
        f"\nhit@{misura.top_k}: {misura.hit_at_k}/{misura.totale}    "
        f"hit@1: {misura.hit_at_1}/{misura.totale}    "
        f"nessun risultato sopra soglia: {misura.vuoti}/{misura.totale}"
    )

    USCITA.mkdir(parents=True, exist_ok=True)
    (USCITA / f"{args.etichetta}.json").write_text(
        misura.model_dump_json(indent=2), encoding="utf-8"
    )
    print(f"scritto docs/eval/{args.etichetta}.json")


if __name__ == "__main__":
    asyncio.run(main())
