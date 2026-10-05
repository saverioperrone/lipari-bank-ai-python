# tests/unit/test_traccia.py — la prova della traccia: il run si ricostruisce dalle agent_step
import logging
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.deps import Deps
from src.agents.loop import run_agent
from src.agents.tools import build_tools_for
from src.auth.deps import UserContext
from src.db.models import ComplianceAlert
from src.services.retrieval_service import RetrievalResult
from tests.conftest import CLIENTE_DI_MARCO, CONTO_DI_MARCO, risposta


async def test_dalle_righe_agent_step_si_ricostruisce_il_run(
    deps_reali: Deps, session: AsyncSession, marco: UserContext, caplog: pytest.LogCaptureFixture
) -> None:
    # il recupero vero vuole PostgreSQL: qui restituisce il passaggio della regola di sportello
    recupero = MagicMock()
    recupero.search_for_user = AsyncMock(
        return_value=[
            RetrievalResult(
                chunk_id="c1",
                document_id="paesi_rischio_elevato",
                content="Un bonifico verso un paese dell'elenco sopra €15.000 non si esegue.",
                similarity=0.8,
            )
        ]
    )
    deps = replace(deps_reali, retrieval=recupero)
    conto = f'"account_id": "{CONTO_DI_MARCO}"'
    client = AsyncMock()
    client.chat.completions.create.side_effect = [  # la domanda del Focus: sei chiamate
        risposta(
            tool="find_customer_accounts", argomenti=f'{{"customer_id": "{CLIENTE_DI_MARCO}"}}'
        ),
        risposta(tool="get_account_balance", argomenti=f"{{{conto}}}"),
        risposta(tool="search_documents", argomenti='{"query": "bonifici verso paesi a rischio"}'),
        risposta(tool="list_recent_movements", argomenti=f'{{{conto}, "n": 10}}'),
        risposta(
            tool="apri_segnalazione_compliance",
            argomenti=f'{{{conto}, "motivo": "Bonifico di 25.000 euro verso il Venezuela", '
            '"importo": "25000"}',
        ),
        risposta(testo="Il bonifico non si esegue allo sportello: segnalazione aperta."),
    ]
    with caplog.at_level(logging.INFO):
        run = await run_agent(
            messaggi=[{"role": "user", "content": "bonifico di 25.000 verso il Venezuela?"}],
            tools=build_tools_for(marco, deps),
            client=client,
            model="gpt-4o-mini",
        )

    # da qui in poi solo le righe agent_step di questo run, come le leggerebbe un audit
    passi = [
        r.__dict__
        for r in caplog.records
        if r.message == "agent_step" and r.__dict__["run_id"] == run.run_id
    ]
    # quali tool, in che ordine, con che esito
    assert [(p["step"], p["tool"], p["result_kind"]) for p in passi] == [
        (1, "find_customer_accounts", "ok"),
        (2, "get_account_balance", "ok"),
        (3, "search_documents", "ok"),
        (4, "list_recent_movements", "ok"),
        (5, "apri_segnalazione_compliance", "ok"),
    ]
    # gli argomenti non ci sono, ma l'impronta dice che saldo e movimenti chiedevano lo stesso conto
    assert passi[1]["tool_args"]["account_id"] == passi[3]["tool_args"]["account_id"]
    assert passi[4]["tool_args"] == "<omessi>"
    # e quale pratica è stata aperta: la ricevuta porta il numero che sta nel database
    alert = await session.scalar(select(ComplianceAlert))
    assert alert is not None
    ricevute = [p["receipt"] for p in passi if p["receipt"]]
    assert len(ricevute) == 1 and alert.id in ricevute[0]
