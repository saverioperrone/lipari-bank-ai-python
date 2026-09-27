"""Carica data/docs/*.md nell'indice passando dall'endpoint HTTP.

    uv run python -m scripts.ingest_docs

Passa dall'endpoint e non dal servizio di proposito: quello che si vuole dimostrare
e' la pipeline che usera' il consulente, non una scorciatoia che salta il router.
Rilanciarlo e' la prova del doppio caricamento: i passaggi sostituiscono, non si sommano.
"""

import asyncio
from pathlib import Path

import httpx

DOCS = Path(__file__).parent.parent / "data" / "docs"
URL = "http://127.0.0.1:8000/api/ai/documents/ingest"

# L'ingestione e' lenta per costruzione: un documento intero sono decine di embedding in
# sequenza. Con il modello locale su CPU i 60 secondi del corso non bastano sempre.
TIMEOUT = 300.0


async def main() -> None:
    percorsi = await asyncio.to_thread(lambda: sorted(DOCS.glob("*.md")))
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for path in percorsi:
            # leggere un file e' bloccante: dentro una coroutine si sposta su un thread
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            response = await client.post(
                URL,
                json={
                    "document_id": path.stem,
                    "content": content,
                    "metadata": {"source": str(path), "title": path.stem.replace("-", " ")},
                },
            )
            response.raise_for_status()
            print(f"{path.name}: {response.json()}")


if __name__ == "__main__":
    asyncio.run(main())
