from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.llm.factory import get_llm_provider
from src.services.chat_service import ChatService
from src.types.chat import ChatRequest, ChatResponse
from pathlib import Path


router = APIRouter(prefix="/api/ai", tags=["Chat"])

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "chat_system_v1.md").read_text()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    service = ChatService(db, get_llm_provider(), SYSTEM_PROMPT)
    return await service.chat(req, user_id="dummy-user")

@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    service = ChatService(db, get_llm_provider(), SYSTEM_PROMPT)

    async def event_generator():
        async for chunk in service.chat_stream(req, user_id="dummy-user"):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
