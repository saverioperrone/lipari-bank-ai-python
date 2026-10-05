import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Computed, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

# Dimensione dei vettori prodotti dal modello di embedding in uso.
# nomic-embed-text ne produce 768; text-embedding-3-small di OpenAI 1536.
# Cambiare modello di embedding significa rifare l'indice da zero: i vettori
# di due modelli diversi non sono confrontabili fra loro.
EMBEDDING_DIM = 768


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String, comment="'system' | 'user' | 'assistant' | 'tool'")
    content: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_eur: Mapped[float] = mapped_column(default=0.0)
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="operator")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class DocumentChunk(Base):
    """Un passaggio di un documento, con il suo vettore.

    `document_id` e `chunk_index` servono a comporre le citazioni: senza sapere
    da quale documento viene un passaggio non si puo' dire all'utente dove
    verificare.
    """

    __tablename__ = "document_chunks"
    # I due indici e la colonna `content_tsv` li hanno creati in SQL le migration del
    # Giorno 5. Dichiararli qui fa coincidere modello e database: senza, l'autogenerate
    # li legge come oggetti da cancellare e `alembic check` non passa.
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_document_chunks_content_tsv", "content_tsv", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(String, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Colonna generata: la ricalcola Postgres da `content`, l'applicazione non la scrive mai.
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('italian', content)", persisted=True)
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    chunk_metadata: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    # Giorno 6. server_default: nella migration, le righe che ci sono già ricevono "public"
    visibility: Mapped[str] = mapped_column(
        String(32), default="public", server_default="public", index=True
    )
