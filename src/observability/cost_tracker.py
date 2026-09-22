from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ChatMessage
from src.exceptions import RateLimitError


class CostTracker:
    def __init__(self, session: AsyncSession, max_eur_per_day: float) -> None:
        self.session = session
        self.max_eur_per_day = max_eur_per_day

    async def daily_cost(self, target_date: date | None = None) -> float:
        day = target_date or date.today()
        stmt = select(func.sum(ChatMessage.cost_eur)).where(
            func.date(ChatMessage.created_at) == day
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() or 0.0

    async def check_budget(self) -> None:
        if await self.daily_cost() >= self.max_eur_per_day:
            raise RateLimitError(retry_after_seconds=3600)
