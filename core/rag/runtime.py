from __future__ import annotations

from core.rag.connection import rag_connection
from core.rag.migrations import apply_rag_migrations
from core.rag.schema_sql import RAG_MIGRATIONS


def initialize_rag_database(dsn: str | None = None) -> None:
    """Inicijalizuje RAG bazu i primenjuje sve registrovane migracije."""
    with rag_connection(dsn) as connection:
        apply_rag_migrations(connection, RAG_MIGRATIONS)
