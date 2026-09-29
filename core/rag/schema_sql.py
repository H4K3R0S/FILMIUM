from __future__ import annotations

from core.rag.migrations import RagMigration

NODE_TYPES: tuple[tuple[str, str, str], ...] = (
    ("pillar", "governance", "Temeljni princip / bezbednosno pravilo"),
    ("decision", "governance", "Arhitekturna odluka (ADR)"),
    ("policy", "governance", "Pravilo namespace-a i pristupa"),
    ("concept", "knowledge", "Definisan pojam / profil brenda"),
    ("reference", "knowledge", "Manifest, domain doc, README"),
    ("spec", "knowledge", "Dizajn spec"),
    ("plan", "knowledge", "Implementacioni plan"),
    ("code_unit", "code", "Funkcija/klasa/modul chunk"),
    ("pattern", "code", "Code-smell / anti-pattern / sablon"),
    ("test", "code", "Test ili gold-set eval"),
    ("task", "code", "Operativni korak"),
    ("playbook", "code", "Korak-po-korak procedura"),
    ("vulnerability", "security", "Ranjivost / bug"),
    ("exploit", "security", "PoC / payload"),
    ("mitigation", "security", "Zakrpa ranjivosti"),
    ("finding", "security", "OSINT/recon/analytics rezultat"),
    ("media_asset", "content", "Profil filma/serije, artwork"),
    ("source", "content", "Transkript / sirov materijal / link"),
    ("hypothesis", "content", "Pretpostavka za rast/algoritam"),
    ("event", "content", "Zakazani strim/objava/marker"),
    ("agent_profile", "system", "Konfiguracija/uloga agenta"),
    ("telemetry", "system", "Perf/mrezni logovi"),
    ("log", "system", "Dev-log / journal"),
    ("archive", "system", "Zastarelo"),
)

# (name, default_weight, decay_exempt)
EDGE_TYPES: tuple[tuple[str, float, bool], ...] = (
    ("contradicts", 1.0, True),
    ("depends_on", 0.9, True),
    ("resolves", 1.0, True),
    ("derived_from", 1.0, True),
    ("owned_by", 1.0, True),
    ("caused_by", 0.9, False),
    ("followed_by", 0.8, False),
    ("preceded_by", 0.8, False),
    ("implements", 0.8, False),
    ("triggers", 0.8, False),
    ("tested_by", 0.8, False),
    ("supersedes", 0.9, False),
    ("supports", 0.7, False),
    ("duplicates", 0.6, False),
    ("belongs_to", 0.5, False),
    ("references", 0.3, False),
)


def _seed_node_types() -> str:
    redovi = ", ".join(f"('{n}', '{t}', '{o}')" for n, t, o in NODE_TYPES)
    return (
        "INSERT INTO node_types (name, tier, description) VALUES "
        f"{redovi} ON CONFLICT (name) DO NOTHING"
    )


def _seed_edge_types() -> str:
    redovi = ", ".join(
        f"('{n}', {w}, {str(e).lower()})" for n, w, e in EDGE_TYPES
    )
    return (
        "INSERT INTO edge_types (name, default_weight, decay_exempt) VALUES "
        f"{redovi} ON CONFLICT (name) DO NOTHING"
    )


_V1_TABELE = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE node_types (
        name text PRIMARY KEY,
        tier text NOT NULL,
        description text
    )
    """,
    """
    CREATE TABLE edge_types (
        name text PRIMARY KEY,
        default_weight real NOT NULL,
        decay_exempt boolean NOT NULL DEFAULT false
    )
    """,
    """
    CREATE TABLE nodes (
        id text PRIMARY KEY,
        domain text NOT NULL,
        node_type text NOT NULL REFERENCES node_types(name),
        subtype text,
        namespace text NOT NULL,
        visibility text NOT NULL,
        tier text NOT NULL,
        owner_agent text,
        title text NOT NULL,
        summary text,
        keywords text[] NOT NULL DEFAULT '{}',
        tags text[] NOT NULL DEFAULT '{}',
        symbols text[] NOT NULL DEFAULT '{}',
        source_path text,
        span_start int,
        span_end int,
        content_hash text,
        attributes jsonb NOT NULL DEFAULT '{}',
        status text NOT NULL DEFAULT 'active',
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        last_used_at timestamptz
    )
    """,
    """
    CREATE TABLE chunks (
        id text PRIMARY KEY,
        node_id text NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        ordinal int NOT NULL,
        content text NOT NULL,
        token_count int NOT NULL,
        embedding vector(768),
        fts tsvector
    )
    """,
    """
    CREATE TABLE edges (
        src text NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        dst text NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        edge_type text NOT NULL REFERENCES edge_types(name),
        weight real NOT NULL,
        state text NOT NULL DEFAULT 'active',
        decay_exempt boolean NOT NULL DEFAULT false,
        last_used_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (src, dst, edge_type)
    )
    """,
    """
    CREATE TABLE shallow_index (
        node_id text PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
        domain text NOT NULL,
        node_type text NOT NULL,
        title text NOT NULL,
        summary text,
        keywords text[] NOT NULL DEFAULT '{}',
        tags text[] NOT NULL DEFAULT '{}',
        fts tsvector
    )
    """,
    """
    CREATE TABLE clipboard (
        key text PRIMARY KEY,
        state jsonb NOT NULL,
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)",
    "CREATE INDEX ON chunks USING gin (fts)",
    "CREATE INDEX ON shallow_index USING gin (fts)",
    "CREATE INDEX ON nodes USING gin (tags)",
    "CREATE INDEX ON nodes USING gin (symbols)",
    "CREATE INDEX ON nodes USING gin (attributes)",
    "CREATE INDEX ON nodes (domain, node_type, namespace)",
    "CREATE INDEX ON nodes (owner_agent)",
    "CREATE INDEX ON edges (dst, edge_type)",
    _seed_node_types(),
    _seed_edge_types(),
)

RAG_MIGRATIONS: tuple[RagMigration, ...] = (
    RagMigration(1, "temelj_seme_v1", _V1_TABELE),
)
