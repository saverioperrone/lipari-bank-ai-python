# tests/unit/test_doppia_firma.py — l'estensione: sopra la seconda soglia firmano in due
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
from sqlalchemy import func, select

from src.db.models import AgentRunState, ComplianceAlert
from tests.banco_app import crea_app, prepara_db
from tests.conftest import CONTO_DI_MARCO, risposta

SEGNALA_60K = (
    f'{{"account_id": "{CONTO_DI_MARCO}", '
    '"motivo": "Bonifico da 60.000 euro verso il Venezuela", "importo": "60000"}'
)


async def test_sopra_la_seconda_soglia_firmano_due_responsabili_diversi(tmp_path: Path) -> None:
    fabbrica = await prepara_db(tmp_path / "banca.db")
    modello = AsyncMock()
    modello.chat.completions.create.side_effect = [
        risposta(tool="apri_segnalazione_compliance", argomenti=SEGNALA_60K),
        risposta(testo="Segnalazione aperta."),
    ]

    async def segnalazioni() -> int:
        async with fabbrica() as s:
            return await s.scalar(select(func.count()).select_from(ComplianceAlert)) or 0

    async def stato_nel_database(run_id: str) -> AgentRunState:
        async with fabbrica() as s:
            stato = await s.get(AgentRunState, run_id)
        assert stato is not None
        return stato

    app = crea_app(fabbrica, modello)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/api/ai/agent", headers={"X-Utente": "mbianchi"}, json={"message": "?"})
        run_id = r.json()["run_id"]
        url = f"/api/ai/agent/{run_id}/approve"

        # la prima firma: lo stato intermedio ha un nome, sta nel database, e niente è partito
        prima = await c.post(url, headers={"X-Utente": "grossi"})
        assert prima.json()["stopped_by"] == "awaiting_second_approval"
        assert (await stato_nel_database(run_id)).status == "awaiting_second_approval"
        assert await segnalazioni() == 0

        # la seconda firma non può essere la prima: né un 200, né una segnalazione
        assert (await c.post(url, headers={"X-Utente": "grossi"})).status_code == 403
        assert await segnalazioni() == 0

        # un altro responsabile: il run riparte, e la segnalazione c'è adesso
        seconda = await c.post(url, headers={"X-Utente": "lverdi"})
        assert seconda.json()["stopped_by"] == "model"
        assert await segnalazioni() == 1

    stato = await stato_nel_database(run_id)
    assert stato.status == "done"
    assert [(d["da"], d["esito"]) for d in stato.decisions] == [
        ("grossi", "prima firma"),
        ("lverdi", "approvata"),
    ]
