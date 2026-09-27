"""document_chunks con pgvector

Revision ID: 765626aa9162
Revises: 8521ccc4c0dc
Create Date: 2026-09-25 15:47:12.882717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy  # l'autogenerazione lo usa ma non lo importa


# revision identifiers, used by Alembic.
revision: str = '765626aa9162'
down_revision: Union[str, Sequence[str], None] = '8521ccc4c0dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # L'estensione non e' un modello, quindi l'autogenerazione non la produce:
    # va scritta a mano, o su un database pulito la colonna vector non esiste.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('document_chunks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
    sa.Column('chunk_metadata', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)

    # Indice HNSW con l'operatore coseno: dev'essere lo stesso operatore usato
    # nell'ORDER BY della query, altrimenti la ricerca scansiona tutto in silenzio.
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
