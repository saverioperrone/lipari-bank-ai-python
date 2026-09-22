from sqlalchemy.ext.asyncio import AsyncSession
from datetime import UTC, datetime

from src.config import settings
from src.db.repos import ChatRepository
from src.llm.client import LLMProvider, Message
from src.exceptions import ChatSessionNotFoundError
from src.observability.cost_tracker import CostTracker
from src.types.chat import ChatRequest, ChatResponse
from collections.abc import AsyncGenerator


class ChatService:
    def __init__(self, session: AsyncSession, llm: LLMProvider, system_prompt: str) -> None:
        self.session = session
        self.repo = ChatRepository(session)
        self.llm = llm
        self.system_prompt = system_prompt
        self.cost_tracker = CostTracker(session, settings.max_eur_per_day)

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
            chat.id, "assistant", llm_response.content,
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

    async def chat_stream(self, req: ChatRequest, user_id: str) -> AsyncGenerator[str, None]:
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
        # Funziona quindi solo con un modello OpenAI selezionato.
        stream = await self.llm.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[m.model_dump() for m in messages],
            stream=True,
            max_tokens=500,
        )

        full_reply = ""
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_reply += delta
                yield delta  # SSE chunk

        # Salva assistant message a fine stream
        await self.repo.add_message(chat.id, "assistant", full_reply)
        await self.session.commit()
