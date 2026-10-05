"""Access control list: quali livelli di visibilità vede ciascun ruolo."""

import logging

log = logging.getLogger(__name__)

_PUBLIC: list[str] = ["public"]
_OPERATIVO: list[str] = ["public", "internal"]

_MATRICE: dict[str, list[str]] = {
    "admin": ["public", "internal", "risk_only", "compliance_only"],
    "compliance_lead": ["public", "internal", "compliance_only"],
    "risk_lead": ["public", "internal", "risk_only"],
    "operator": _OPERATIVO,
}


def visible_to(role: str) -> list[str]:
    """Livelli visibili al ruolo. Un ruolo non riconosciuto vede solo il pubblico."""
    livelli = _MATRICE.get(role)
    if livelli is None:
        # il default sicuro non basta: un ruolo sconosciuto e' un token vecchio o un
        # servizio nuovo, e senza questa riga nessuno si accorge che vede meno di prima
        log.warning("ruolo_sconosciuto", extra={"role": role})
        return _PUBLIC
    return livelli
