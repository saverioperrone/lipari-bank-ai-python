"""ricerca lessicale su document_chunks

Revision ID: a1c4e7d20f31
Revises: 765626aa9162
Create Date: 2026-09-25

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c4e7d20f31'
down_revision: Union[str, Sequence[str], None] = '765626aa9162'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Colonna generata e non riempita dall'applicazione: Postgres la ricalcola da solo
    # a ogni scrittura di `content`, quindi l'ingestione non cambia di una riga e non
    # esiste il caso in cui il testo e' aggiornato e l'indice lessicale no.
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('italian', content)) STORED"
    )
    # GIN e' l'indice per il testo, come HNSW lo e' per i vettori.
    op.execute(
        "CREATE INDEX ix_document_chunks_content_tsv ON document_chunks "
        "USING gin (content_tsv)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_tsv")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsv")
