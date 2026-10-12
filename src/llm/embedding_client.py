from openai import AsyncOpenAI


class EmbeddingClient:
    """Vettorizza testi con il modello di embedding configurato.

    Punta a Ollama tramite `base_url`, che espone un endpoint compatibile con
    le API OpenAI: il corso usa `text-embedding-3-small`, qui non ci sono chiavi
    a pagamento e si usa un modello locale. La classe resta la stessa.
    """

    # Giorno 10: client e modello arrivano da fuori, come nel Code Blueprint del Giorno 5: li
    # passa la factory, e un test può passare un client finto
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

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
