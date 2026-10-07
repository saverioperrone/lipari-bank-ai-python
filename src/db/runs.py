# src/db/runs.py — lo stato dei run sospesi: si scrive, si rilegge, si decide una volta sola
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRunState

# l'esito che resta nello storico, per lo stato in cui la decisione porta il run.
# La prima firma è dell'estensione: il run aspetta la seconda, e niente è partito
ESITI = {"running": "approvata", "rejected": "respinta", "awaiting_second_approval": "prima firma"}


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sospendi(
        self,
        *,
        run_id: str,
        username: str,
        role: str,
        messages: list[dict[str, Any]],
        pending_calls: list[dict[str, Any]],
        description: str,
        steps: int,
        cost_eur: Decimal,
        tool_calls: list[str],
    ) -> None:
        """Salva il run in attesa. `merge`: lo stesso run può fermarsi più di una volta.

        `decisions` non è fra i campi: il merge non lo tocca, e le firme di prima restano.
        """
        await self.session.merge(
            AgentRunState(
                id=run_id,
                username=username,
                role=role,
                status="awaiting_approval",
                messages=messages,
                pending_calls=pending_calls,
                description=description,
                steps=steps,
                cost_eur=cost_eur,
                tool_calls=tool_calls,
                decided_by=None,
                decision_reason=None,
            )
        )
        await self.session.commit()

    async def get(self, run_id: str) -> AgentRunState | None:
        return await self.session.get(AgentRunState, run_id)

    async def decidi(
        self,
        run_id: str,
        *,
        da: str,
        stato: str,
        motivo: str | None,
        in_attesa: str = "awaiting_approval",
    ) -> bool:
        """Esce dall'attesa, solo se era in attesa. Il bool dice se questa decisione ha vinto.

        È un UPDATE condizionato, non un «leggi e poi scrivi»: con due clic insieme uno solo
        trova la riga in attesa, e l'altro riceve False.

        Estensione: `in_attesa` è lo stato da cui si esce. Dalla seconda firma esce solo chi
        non ha messo la prima, e la condizione sta nello stesso UPDATE.
        """
        condizioni = [AgentRunState.id == run_id, AgentRunState.status == in_attesa]
        if in_attesa == "awaiting_second_approval":
            condizioni.append(AgentRunState.decided_by != da)
        esito = await self.session.execute(
            update(AgentRunState)
            .where(*condizioni)
            .values(
                status=stato, decided_by=da, decision_reason=motivo, updated_at=datetime.now(UTC)
            )
        )
        vinta = bool(getattr(esito, "rowcount", 0))
        if vinta:
            # nello storico, nella stessa transazione: chi ha deciso cosa, prima che l'azione parta
            riga = await self.session.get(AgentRunState, run_id, populate_existing=True)
            if riga is not None:
                decisione = {
                    "da": da,
                    "esito": ESITI[stato],
                    "motivo": motivo,
                    "azione": riga.description,
                    "quando": datetime.now(UTC).isoformat(),
                }
                riga.decisions = [*riga.decisions, decisione]  # una lista nuova: il JSON cambia
        await self.session.commit()
        return vinta

    async def chiudi(self, run_id: str, stato: str) -> None:
        # La decisione del Giorno 8: la conversazione serve solo a riprendere, e porta IBAN,
        # saldi e passaggi dei documenti. A run chiuso si svuota: per l'audit restano
        # `description` e `decisions`
        await self.session.execute(
            update(AgentRunState)
            .where(AgentRunState.id == run_id)
            .values(status=stato, messages=[], pending_calls=[], updated_at=datetime.now(UTC))
        )
        await self.session.commit()
