# scripts/bench_cache.py — gli stessi passaggi due volte, con la cache davanti
"""Quanto costa la prima passata, quanto la seconda.

I testi sono i passaggi veri di data/docs/, tagliati come li taglia l'ingestione, quindi la
misura è quella che paghi. Prima si cancellano solo le loro chiavi: il resto di Redis
(riscritture, rate limit) non si tocca.

docker compose exec api python -m scripts.bench_cache
"""

import asyncio
import time
from pathlib import Path

from src.cache import get_redis
from src.config import settings
from src.lib.chunking import chunk_text
from src.llm.embedding_client import EmbeddingClient
from src.llm.embeddings import CachedEmbedder
from src.llm.factory import get_embedder

# nomic-embed-text gira in locale, su Ollama: il prezzo vero è zero, e il numero che conta è il
# tempo. Il Code Blueprint qui ha il listino di text-embedding-3-small
EURO_PER_MILIONE_DI_TOKEN = 0.0
LOTTO = 64


def stima_eur(testi: list[str]) -> float:
    # circa quattro caratteri per token: è una stima, e il report lo deve dire
    return sum(len(t) for t in testi) / 4 / 1_000_000 * EURO_PER_MILIONE_DI_TOKEN


def passaggi(n: int = 100) -> list[str]:
    """I passaggi del corpus, compresi i documenti nelle sottocartelle dei livelli."""
    return [
        pezzo
        for f in sorted(Path("data/docs").rglob("*.md"))
        for pezzo in chunk_text(f.read_text(encoding="utf-8"))
    ][:n]


async def main(testi: list[str]) -> None:
    redis = get_redis()
    if redis is None:
        raise SystemExit("REDIS_URL è vuota: senza Redis non c'è una cache da misurare.")
    if not testi:
        raise SystemExit("Nessun passaggio in data/docs/: niente da misurare.")

    # il client degli embedding è quello della factory: qui di Ollama, non quello di OpenAI
    emb = CachedEmbedder(EmbeddingClient(get_embedder().client, settings.embedding_model), redis)
    await redis.delete(*[emb.chiave(t) for t in testi])

    for nome in ("cache vuota", "cache piena"):
        prima = emb.miss
        inizio = time.perf_counter()
        for i in range(0, len(testi), LOTTO):
            await emb.embed(testi[i : i + LOTTO])
        durata = time.perf_counter() - inizio
        pagati = emb.miss - prima
        costo = stima_eur(testi) * pagati / len(testi)
        print(
            f"{nome}: {len(testi)} passaggi in {durata:.2f}s   "
            f"costo stimato EUR {costo:.6f}  ({len(testi) - pagati} dalla cache)"
        )
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main(passaggi()))  # i file si leggono prima, fuori dal loop
