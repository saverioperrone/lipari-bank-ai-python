# tests/unit/test_budget_stimato.py — l'estensione 2: il budget si controlla anche prima
from unittest.mock import AsyncMock

from src.agents.deps import Deps
from src.agents.loop import run_agent
from src.agents.tools import build_tools_for
from src.auth.deps import UserContext
from tests.conftest import CONTO_DI_MARCO, risposta


async def test_la_chiamata_che_sfonderebbe_il_budget_non_parte(
    deps_reali: Deps, marco: UserContext
) -> None:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        # la prima costa 0,0497 euro: sotto il budget di 0,05, e il controllo di dopo la lascia
        # passare. La seconda lo sfonderebbe: la stima la ferma prima che parta
        risposta(
            tool="get_account_balance",
            argomenti=f'{{"account_id": "{CONTO_DI_MARCO}"}}',
            prompt_tokens=355_000,
        ),
        risposta(testo="Questa risposta non deve arrivare: costerebbe oltre il budget."),
    ]
    run = await run_agent(
        messaggi=[{"role": "user", "content": "saldo del conto principale"}],
        tools=build_tools_for(marco, deps_reali),
        client=client,
        model="gpt-4o-mini",
    )
    assert (run.stopped_by, run.steps, run.tool_calls) == ("budget", 1, ["get_account_balance"])
    assert client.chat.completions.create.call_count == 1  # la seconda non è stata pagata
