from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repos import ChatRepository
from src.exceptions import ChatSessionNotFoundError, LLMProviderError
from src.llm.client import LLMProvider
from src.llm.ollama_provider import OllamaProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.types import Message
from src.observability.cost_tracker import CostTracker
from src.types.chat import ChatRequest, ChatResponse


class ChatService:
    def __init__(
        self, session: AsyncSession, llm: LLMProvider, system_prompt: str, daily_budget_eur: float
    ) -> None:
        self.session = session
        self.repo = ChatRepository(session)
        self.llm = llm
        self.system_prompt = system_prompt
        self.cost_tracker = CostTracker(session, daily_budget_eur)

    async def chat(self, req: ChatRequest, user_id: str) -> ChatResponse:
        # Prima di qualunque scrittura e prima di spendere: se il tetto
        # giornaliero e' gia' stato raggiunto, RateLimitError diventa un 429.
        await self.cost_tracker.check_budget()

        if req.session_id != "new":
            chat = await self.repo.find_session(req.session_id)
            if not chat:
                raise ChatSessionNotFoundError(req.session_id)
        else:
            chat = await self.repo.create_session(user_id=user_id)

        # Build history
        history_messages = await self.repo.list_messages(chat.id)
        messages: list[Message] = [Message(role="system", content=self.system_prompt)]
        for m in history_messages:
            messages.append(Message(role=m.role, content=m.content))
        messages.append(Message(role="user", content=req.message))

        # Save user message
        await self.repo.add_message(chat.id, "user", req.message)

        # Call LLM
        llm_response = await self.llm.complete(messages, max_tokens=500)

        # Save assistant message
        await self.repo.add_message(
            chat.id,
            "assistant",
            llm_response.content,
            tokens=llm_response.tokens_used,
            cost_eur=llm_response.cost_eur,
            model_used=llm_response.model,
        )

        await self.session.commit()

        return ChatResponse(
            session_id=chat.id,
            reply=llm_response.content,
            tokens_used=llm_response.tokens_used,
            cost_eur=llm_response.cost_eur,
            model_used=llm_response.model,
            created_at=datetime.now(UTC),
        )

    async def chat_stream(self, req: ChatRequest, user_id: str) -> AsyncIterator[str]:
        """Fa subito i controlli e restituisce lo stream, che si legge dopo.

        Budget, sessione e apertura dello stream avvengono qui, quando l'endpoint fa
        `await`: un 429 o un 404 arrivano al client come tali. Dentro il generatore
        partirebbero solo alla prima lettura, quando lo `StreamingResponse` ha gia'
        mandato il 200, e il client riceverebbe una risposta vuota.
        """
        await self.cost_tracker.check_budget()

        if req.session_id != "new":
            chat = await self.repo.find_session(req.session_id)
            if not chat:
                raise ChatSessionNotFoundError(req.session_id)
        else:
            chat = await self.repo.create_session(user_id=user_id)

        history_messages = await self.repo.list_messages(chat.id)
        messages: list[Message] = [Message(role="system", content=self.system_prompt)]
        for m in history_messages:
            messages.append(Message(role=m.role, content=m.content))
        messages.append(Message(role="user", content=req.message))

        await self.repo.add_message(chat.id, "user", req.message)

        # Nota: lo streaming passa dal client OpenAI del provider, non dal Protocol
        # (il blocco 4.3 della consegna dichiara il solo `complete`).
        # Funziona quindi solo con i provider che hanno un client OpenAI: OpenAI e Ollama.
        if not isinstance(self.llm, OpenAIProvider | OllamaProvider):
            raise LLMProviderError(type(self.llm).__name__, "streaming non supportato")
        stream = await self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=cast(list[ChatCompletionMessageParam], [m.model_dump() for m in messages]),
            stream=True,
            max_tokens=500,
        )

        async def pezzi() -> AsyncIterator[str]:
            full_reply = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_reply += delta
                    yield delta  # SSE chunk

            # Salva assistant message a fine stream
            await self.repo.add_message(chat.id, "assistant", full_reply)
            await self.session.commit()

        return pezzi()
