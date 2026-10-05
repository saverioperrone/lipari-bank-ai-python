import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.passwords import hash_password, verify_password
from src.auth.tokens import create_access_token
from src.db.models import AppUser
from src.db.session import get_db
from src.types.auth import TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

log = logging.getLogger(__name__)

# Se l'utente non esiste la password si verifica lo stesso, contro questo hash: senza, quel
# ramo risponderebbe subito, e il tempo di risposta direbbe quali username esistono.
DUMMY_HASH = hash_password("nessun-utente-ha-questa-password")


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Verifica le credenziali ed emette un access token a scadenza.

    Credenziali sbagliate: 401, e il messaggio NON dice quale delle due era sbagliata.
    """
    user = await db.scalar(select(AppUser).where(AppUser.username == form.username))
    hash_da_verificare = user.password_hash if user is not None else DUMMY_HASH
    password_giusta = verify_password(form.password, hash_da_verificare)
    if user is None or not password_giusta:
        # all'esterno una frase sola; nel log la distinzione resta, perche' serve:
        # cento «utente inesistente» di fila sono una scansione
        motivo = "utente_inesistente" if user is None else "password_errata"
        log.warning("login_fallito", extra={"username": form.username, "motivo": motivo})
        raise HTTPException(401, "Credenziali non valide")
    return TokenResponse(access_token=create_access_token(user.username, user.role))
