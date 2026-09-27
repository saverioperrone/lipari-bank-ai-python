"""Carica corpus/*.md nell'indice passando dall'endpoint HTTP.

    uv run python -m scripts.ingest_corpus

Passa dall'endpoint e non dal servizio di proposito: quello che si vuole dimostrare
e' la pipeline che usera' il consulente, non una scorciatoia che salta il router.
Rilanciarlo e' la prova del doppio caricamento: i passaggi sostituiscono, non si sommano.
"""

import asyncio
from pathlib import Path

import httpx

CORPUS = Path(__file__).parent.parent / "corpus"
URL = "http://127.0.0.1:8000/api/ai/documents/ingest"


async def main() -> None:
    # L'ingestione e' lenta per costruzione: un documento intero sono decine di
    # embedding in sequenza. Il timeout generoso e' la nota della lezione, non un cerotto.
    async with httpx.AsyncClient(timeout=300.0) as client:
        for doc in sorted(CORPUS.glob("*.md")):
            r = await client.post(
                URL,
                json={"document_id": doc.stem, "content": doc.read_text(encoding="utf-8")},
            )
            r.raise_for_status()
            body = r.json()
            print(f"{doc.stem:42} {body['chunk_count']:3} passaggi  dim {body['embedding_dim']}")


if __name__ == "__main__":
    asyncio.run(main())
