# tests/test_g10.py — le cache condivise, la loro caduta, le due sonde, il seed che si ripete
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal

import fakeredis
import httpx2
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

import src.main
from scripts import misura_tetti
from src.api.advice import get_rewriter
from src.config import Settings
from src.db.models import EMBEDDING_DIM, AppUser, Customer, DocumentChunk
from src.db.session import AsyncSessionLocal, engine
from src.llm import factory
from src.llm.embedding_client import EmbeddingClient
from src.llm.embeddings import CachedEmbedder
from src.llm.factory import get_llm_provider
from src.llm.rewriter import QueryRewriter
from src.main import app
from src.services.ingest_service import IngestService
from tests.finti import ModelloFisso, Registro, embedder_finto, gestore_embedding, openai_finto

PUBBLICO = "# Bonifici estero\nI bonifici verso il Venezuela sono extra-SEPA: costo €15.00."


@pytest.fixture(autouse=True)
async def database_pulito() -> AsyncIterator[None]:
    await engine.dispose()
    async with engine.begin() as c:
        await c.execute(
            text(
                "TRUNCATE llm_calls, document_chunks, agent_runs, compliance_alerts, movements, "
                "accounts, customers, app_users, chat_messages, chat_sessions CASCADE"
            )
        )
    yield
    # anche all'uscita: in ordine alfabetico test_g10 gira prima di test_g6, che usa il
    # TestClient con un suo loop, e troverebbe nel pool connessioni aperte da questo
    await engine.dispose()


@pytest.fixture(autouse=True)
def override_ripristinati() -> Iterator[None]:
    prima = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(prima)


@pytest.fixture
def server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()  # un Redis in memoria, che si può anche spegnere


def redis(server: fakeredis.FakeServer) -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(server=server)


def embedder_contato() -> tuple[EmbeddingClient, Registro]:
    reg = Registro()

    def gestore(r: httpx2.Request) -> httpx2.Response:
        reg.annota(r)
        return gestore_embedding(r)

    return EmbeddingClient(openai_finto(gestore), "text-embedding-3-small"), reg


# ---------------------------------------------------------------- la cache degli embedding
async def test_la_cache_degli_embedding_chiede_solo_i_mancanti(
    server: fakeredis.FakeServer,
) -> None:
    base, reg = embedder_contato()
    emb = CachedEmbedder(base, redis(server))
    primi = await emb.embed(["uno", "due"])
    secondi = await emb.embed(["due", "tre", "uno"])  # due già noti, uno nuovo
    assert secondi[0] == primi[1] and secondi[2] == primi[0]
    assert [r["input"] for r in reg.richieste] == [["uno", "due"], ["tre"]]  # un lotto a giro
    assert (emb.hit, emb.miss) == (2, 3)


async def test_un_altro_worker_trova_i_vettori_del_primo(server: fakeredis.FakeServer) -> None:
    base, reg = embedder_contato()
    await CachedEmbedder(base, redis(server)).embed_one("bonifico estero")
    altro = CachedEmbedder(base, redis(server))  # un altro processo, lo stesso Redis
    await altro.embed_one("bonifico estero")
    assert len(reg.richieste) == 1 and altro.hit == 1


async def test_senza_redis_si_paga_ma_si_risponde(server: fakeredis.FakeServer) -> None:
    base, reg = embedder_contato()
    emb = CachedEmbedder(base, redis(server))
    server.connected = False  # Redis giù
    vettore = await emb.embed_one("bonifico estero")
    # le dimensioni del modello di questo progetto, nomic-embed-text: non le 1536 di OpenAI
    assert len(vettore) == EMBEDDING_DIM and len(reg.richieste) == 1


def test_la_factory_mette_la_cache_solo_se_c_e_redis(
    monkeypatch: pytest.MonkeyPatch, server: fakeredis.FakeServer
) -> None:
    assert type(factory.get_embedder()) is EmbeddingClient  # nei test REDIS_URL è vuota
    monkeypatch.setattr(factory, "get_redis", lambda: redis(server))
    emb = factory.get_embedder()
    assert isinstance(emb, CachedEmbedder) and isinstance(emb, EmbeddingClient)


# ---------------------------------------------------------------- la cache delle riscritture
async def test_la_riscrittura_si_paga_una_volta_per_tutti_i_worker(
    server: fakeredis.FakeServer,
) -> None:
    modello = ModelloFisso("operazioni verso il Venezuela")
    primo = await QueryRewriter(modello, "P", cache=redis(server)).riscrivi_per_ricerca("ven ok?")
    secondo = await QueryRewriter(modello, "P", cache=redis(server)).riscrivi_per_ricerca("ven ok?")
    assert (primo.da_cache, primo.cost_eur) == (False, Decimal("0.0001"))
    assert (secondo.da_cache, secondo.cost_eur, secondo.testo) == (
        True,
        Decimal("0"),
        "operazioni verso il Venezuela",
    )
    assert len(modello.ricevuti) == 1


async def test_un_prompt_nuovo_non_legge_la_cache_del_vecchio(
    server: fakeredis.FakeServer,
) -> None:
    await QueryRewriter(ModelloFisso("vecchia"), "P1", cache=redis(server)).rewrite_cached("x?")
    nuova = await QueryRewriter(ModelloFisso("nuova"), "P2", cache=redis(server)).rewrite_cached(
        "x?"
    )
    assert nuova == "nuova"
    chiavi = [
        k.decode() if isinstance(k, bytes) else k for k in await redis(server).keys("rewrite:*")
    ]
    assert len(chiavi) == 2 and not any("x?" in k for k in chiavi)  # l'hash, non la domanda


async def test_con_redis_giu_si_riscrive_lo_stesso(server: fakeredis.FakeServer) -> None:
    server.connected = False
    r = QueryRewriter(ModelloFisso("operazioni verso il Venezuela"), "P", cache=redis(server))
    assert await r.rewrite_cached("ven ok?") == "operazioni verso il Venezuela"


async def test_l_advice_conta_la_riscrittura_e_dice_se_era_in_cache(
    server: fakeredis.FakeServer, caplog: pytest.LogCaptureFixture
) -> None:
    async with AsyncSessionLocal() as s:
        await IngestService(s, embedder_finto()).ingest("bonifici_estero", PUBBLICO)
    modello = ModelloFisso("costo bonifici verso il Venezuela [fonte-1]")
    riscrittore = QueryRewriter(modello, "P", cache=redis(server))
    app.dependency_overrides[get_llm_provider] = lambda: modello
    app.dependency_overrides[get_rewriter] = lambda: riscrittore
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        with caplog.at_level("INFO"):
            prima = (await c.post("/api/ai/advice", json={"question": "ven costo?"})).json()
            dopo = (await c.post("/api/ai/advice", json={"question": "ven costo?"})).json()
    assert prima["cost_eur"] == pytest.approx(0.0002)  # riscrittura + risposta
    assert dopo["cost_eur"] == pytest.approx(0.0001)  # la riscrittura dalla cache
    righe = [r for r in caplog.records if r.message == "advice_completata"]
    assert [r.__dict__["cache_hit"] for r in righe] == [False, True]


# ---------------------------------------------------------------- le due sonde
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_pronto_con_il_database_e_la_cache_spenta() -> None:
    async with client() as c:
        r = await c.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "checks": {"database": "ok", "cache": "spenta"}}


async def test_senza_database_vivo_ma_non_pronto_e_senza_topologia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # un database che non c'è: la porta 1 non risponde, e l'URL ha una password riconoscibile
    spento = create_async_engine("postgresql+asyncpg://lipari:segreta-42@127.0.0.1:1/lipari_ai")
    monkeypatch.setattr(src.main, "engine", spento)
    async with client() as c:
        pronto = await c.get("/ready")
        vivo = await c.get("/health")
    assert pronto.status_code == 503 and pronto.json()["checks"]["database"] == "ko"
    assert "segreta-42" not in pronto.text and "127.0.0.1" not in pronto.text  # niente mappa
    assert vivo.status_code == 200  # la liveness non tocca il database: è viva
    await spento.dispose()


async def test_la_cache_giu_non_toglie_l_istanza_dal_traffico(
    monkeypatch: pytest.MonkeyPatch, server: fakeredis.FakeServer
) -> None:
    server.connected = False
    monkeypatch.setattr(src.main, "get_redis", lambda: redis(server))
    async with client() as c:
        r = await c.get("/ready")
    assert r.status_code == 200 and r.json()["checks"] == {"database": "ok", "cache": "ko"}


# ---------------------------------------------------------------- il seed del compose
async def test_il_seed_si_puo_lanciare_due_volte(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import seed_all

    monkeypatch.setattr("evals.ingest_fixtures.get_embedder", embedder_finto)
    # qui gli embedding sono di Ollama, che non chiede una chiave: la metà del Code Blueprint
    # con il segnaposto di .env.example, che lascia l'indice vuoto, non c'è
    await seed_all.main()
    async with AsyncSessionLocal() as s:
        passaggi = await s.scalar(select(func.count()).select_from(DocumentChunk))
    await seed_all.main()  # il secondo `docker compose up`
    async with AsyncSessionLocal() as s:
        assert await s.scalar(select(func.count()).select_from(AppUser)) == 3
        assert await s.scalar(select(func.count()).select_from(Customer)) == 2
        assert await s.scalar(select(func.count()).select_from(DocumentChunk)) == passaggi
    assert passaggi
    # e il segreto d'esempio di .env.example non fa partire niente
    with pytest.raises(ValidationError):
        Settings(database_url="x", jwt_secret="cambiami-con-python-secrets-token-urlsafe-48")


# ---------------------------------------------------------------- i tetti
def test_i_tetti_si_rispettano_con_un_numero_senza_peggiorare_l_altro() -> None:
    partenza = {"p95_s": 4.0, "costo_medio_eur": 0.0010}
    verdetto = misura_tetti.verdetto
    assert verdetto(partenza, {"p95_s": 2.9, "costo_medio_eur": 0.0010})[0]  # tempo
    assert verdetto(partenza, {"p95_s": 4.0, "costo_medio_eur": 0.0007})[0]  # costo
    assert not verdetto(partenza, {"p95_s": 2.9, "costo_medio_eur": 0.0011})[0]  # costo su
    assert not verdetto(partenza, {"p95_s": 3.5, "costo_medio_eur": 0.0009})[0]  # poco
    assert misura_tetti.p95([1.0] * 19 + [10.0]) < 10.0  # un caso su venti non è il p95
