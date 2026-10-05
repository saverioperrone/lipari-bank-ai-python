from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ChatMessage
from src.exceptions import RateLimitError


class CostTracker:
    def __init__(self, session: AsyncSession, daily_budget_eur: float) -> None:
        self.session = session
        self.daily_budget_eur = daily_budget_eur

    async def daily_cost(self, target_date: date | None = None) -> float:
        day = target_date or date.today()
        stmt = select(func.sum(ChatMessage.cost_eur)).where(
            func.date(ChatMessage.created_at) == day
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() or 0.0

    async def check_budget(self) -> None:
        if await self.daily_cost() >= self.daily_budget_eur:
            raise RateLimitError(retry_after_seconds=3600)
