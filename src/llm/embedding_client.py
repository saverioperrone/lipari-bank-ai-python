from openai import AsyncOpenAI

from src.config import settings


class EmbeddingClient:
    """Vettorizza testi con il modello di embedding configurato.

    Punta a Ollama tramite `base_url`, che espone un endpoint compatibile con
    le API OpenAI: il corso usa `text-embedding-3-small`, qui non ci sono chiavi
    a pagamento e si usa un modello locale. La classe resta la stessa.
    """

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key="ollama", base_url=settings.ollama_base_url)
        self.model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed multiple texts."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def embed_one(self, text: str) -> list[float]:
        result = await self.embed([text])
        return result[0]
