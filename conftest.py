from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def modelli_finti() -> Iterator[None]:
    """Dal Giorno 4 nessun test chiama un modello vero: costerebbe, e risponderebbe ogni volta
    in un modo diverso. La chat parla con un finto che ripete la domanda, gli embedding sono
    finti ma coerenti (dal Giorno 5). E dal Giorno 6 chi chiede è Marco, operatore, senza
    token: i test di autenticazione rimettono il vero. Un test che vuole un modello preciso, o
    un altro utente, mette il suo."""
    from src.api.advice import get_rewriter
    from src.auth.deps import get_current_user
    from src.llm.factory import get_embedder, get_llm_provider
    from src.main import app
    from tests.finti import MARCO, ModelloEco, embedder_finto, riscrittore_spento

    app.dependency_overrides[get_llm_provider] = ModelloEco
    app.dependency_overrides[get_embedder] = embedder_finto
    app.dependency_overrides[get_rewriter] = riscrittore_spento  # dal Giorno 6
    app.dependency_overrides[get_current_user] = lambda: MARCO  # dal Giorno 6: chi chiede
    yield
    app.dependency_overrides.clear()
