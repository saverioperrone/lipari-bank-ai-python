import re

from pydantic import BaseModel
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.acl import visible_to
from src.lib.dedup import senza_ripetizioni
from src.lib.fusione import fondi

SOGLIA_PREDEFINITA = 0.35  # misurata sui documenti di LipariBank, non universale

LUNGHEZZA_MINIMA_PAROLA = 3  # sotto, sono articoli e preposizioni


def parole_in_or(domanda: str) -> str:
    """La domanda ridotta a una `tsquery` che chiede *almeno una* delle sue parole.

    Serve perche' `websearch_to_tsquery` e `plainto_tsquery` mettono le parole in AND:
    con una domanda intera il risultato e' sempre zero righe, perche' nessun passaggio
    contiene tutte le parole della domanda. Con l'OR chi ne contiene di piu' sale in
    cima da solo, che e' il comportamento che serve — `ts_rank_cd` premia proprio i
    passaggi dove le parole cercate sono piu' numerose e piu' vicine fra loro.

    Le parole vengono ridotte a lettere e cifre prima di finire nella query: e' quello
    che rende sicuro passarle a `to_tsquery`, che a differenza delle altre due funzioni
    interpreta gli operatori invece di trattarli come testo.
    """
    parole = [p for p in re.findall(r"\w+", domanda.lower()) if len(p) >= LUNGHEZZA_MINIMA_PAROLA]
    return " | ".join(parole)


class RetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    similarity: float


class RetrievalService:
    """La ricerca vettoriale sui passaggi dei documenti."""

    SQL = sql(
        """
        SELECT id, document_id, content,
               1 - (embedding <=> CAST(:q AS vector)) AS similarity
        FROM document_chunks
        WHERE 1 - (embedding <=> CAST(:q AS vector)) >= :soglia
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :k
        """
    )

    # la SQL di ieri con UNA riga in più: AND visibility = ANY(:livelli)
    SQL_PER_RUOLO = sql(
        """
        SELECT id, document_id, content,
               1 - (embedding <=> CAST(:q AS vector)) AS similarity
        FROM document_chunks
        WHERE 1 - (embedding <=> CAST(:q AS vector)) >= :soglia
          AND visibility = ANY(:livelli)                     -- <- la riga
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :k
        """
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self, query_vec: list[float], top_k: int = 5, soglia: float = SOGLIA_PREDEFINITA
    ) -> list[RetrievalResult]:
        """Ricerca vettoriale SENZA filtro di visibilità.

        Uso consentito: script di ingestione, eval offline, job amministrativi.
        NON usare in un percorso che origina da una richiesta HTTP:
        lì serve search_for_user(), che applica l'ACL nel WHERE.
        """
        righe = await self.session.execute(
            self.SQL, {"q": str(query_vec), "k": top_k, "soglia": soglia}
        )
        return [
            RetrievalResult(
                chunk_id=str(r.id),
                document_id=r.document_id,
                content=r.content,
                similarity=float(r.similarity),
            )
            for r in righe
        ]

    async def search_for_user(
        self,
        query_vec: list[float],
        role: str,
        top_k: int = 5,
        soglia: float = SOGLIA_PREDEFINITA,
    ) -> list[RetrievalResult]:
        """I passaggi più vicini FRA QUELLI che questo ruolo può vedere.

        Il filtro sui livelli sta DENTRO la query, non dopo: il database non deve
        nemmeno restituire i passaggi che questo ruolo non può vedere.
        """
        righe = await self.session.execute(
            self.SQL_PER_RUOLO,
            {"q": str(query_vec), "k": top_k, "soglia": soglia, "livelli": visible_to(role)},
        )
        return [
            RetrievalResult(
                chunk_id=str(r.id),
                document_id=r.document_id,
                content=r.content,
                similarity=float(r.similarity),
            )
            for r in righe
        ]

    # --- ricerca lessicale, aggiunta il Giorno 5 ---------------------------------

    SQL_LESSICALE = sql(
        """
        SELECT id, document_id, content,
               1 - (embedding <=> CAST(:q AS vector)) AS similarity
        FROM document_chunks
        WHERE content_tsv @@ to_tsquery('italian', :parole)
        ORDER BY ts_rank_cd(content_tsv, to_tsquery('italian', :parole)) DESC
        LIMIT :k
        """
    )

    async def search_lessicale(
        self, domanda: str, query_vec: list[float], top_k: int = 5
    ) -> list[RetrievalResult]:
        """I passaggi che contengono le parole della domanda, dal piu' pertinente.

        Nessuna soglia qui: il filtro e' il `@@`, cioe' le parole ci sono o non ci sono.
        La `similarity` riportata resta quella del coseno, calcolata sulla riga che e'
        gia' stata letta: costa niente, e serve a non far uscire dalla ricerca ibrida
        citazioni con un punteggio che non vuol dire piu' la stessa cosa delle altre.
        """
        parole = parole_in_or(domanda)
        if not parole:
            return []
        righe = await self.session.execute(
            self.SQL_LESSICALE, {"q": str(query_vec), "parole": parole, "k": top_k}
        )
        return [
            RetrievalResult(
                chunk_id=str(r.id),
                document_id=r.document_id,
                content=r.content,
                similarity=float(r.similarity),
            )
            for r in righe
        ]

    async def search_ibrida(
        self,
        domanda: str,
        query_vec: list[float],
        top_k: int = 5,
        soglia: float = SOGLIA_PREDEFINITA,
    ) -> list[RetrievalResult]:
        """Le due ricerche, fuse per rango: la lessicale riordina, non introduce.

        La regola che conta e' l'ultima. Un passaggio che la ricerca vettoriale non ha
        recuperato affatto **non entra** nel risultato, per quanto in alto lo metta la
        ricerca lessicale: il ruolo del lessicale e' far salire, fra i candidati che il
        vettore ha gia' trovato, quelli che contengono davvero le parole della domanda.

        Lasciarlo introdurre e' stato provato, e il numero dice di no. Il recupero
        saliva — hit@5 da 8/10 a 10/10 — ma il rifiuto si rompeva: su una domanda la cui
        risposta non sta in nessun documento, tre tentativi su tre rifiutavano col solo
        vettore e zero su tre con la fusione aperta. Il motivo e' che la ricerca
        lessicale trova sempre qualcosa — «conto», «mesi», «tasso» stanno scritti da
        qualche parte — e cinque passaggi che sembrano in tema bastano al modello per
        riempire il buco con un numero inventato.

        I ripetuti si scartano *prima* di fondere, non dopo: una pagina ripetuta occupava
        tre dei cinque posti dell'elenco vettoriale e la fusione la contava come tre
        conferme. Deduplicare dopo non avrebbe rimediato, il rango era gia' assegnato.
        """
        quanti_ne_chiedo = top_k * 3
        vettoriale = await self.search(query_vec, top_k=quanti_ne_chiedo, soglia=soglia)
        lessicale = await self.search_lessicale(domanda, query_vec, top_k=quanti_ne_chiedo)

        candidati = {p.chunk_id for p in vettoriale}
        riordinati = [p for p in lessicale if p.chunk_id in candidati]

        return fondi(
            [
                senza_ripetizioni(vettoriale, top_k, testo=lambda p: p.content),
                senza_ripetizioni(riordinati, top_k, testo=lambda p: p.content),
            ],
            chiave=lambda p: p.chunk_id,
        )[:top_k]
