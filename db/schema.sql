-- Obliviate — CockroachDB schema
-- One transactional store unifies documents + knowledge graph + vectors + crypto + audit.
-- (Replaces the prior project's Cognee + Kùzu + LanceDB split.)

-- Documents: raw ingested text, one row per source document, owned by a subject/entity.
-- content is stored ENCRYPTED under the subject's data key (crypto-shred on erasure).
CREATE TABLE IF NOT EXISTS documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject      STRING NOT NULL,                 -- the data subject / system this doc is about
    title        STRING,
    content_enc  BYTES,                           -- AES-GCM ciphertext of the raw text
    importance   FLOAT8 DEFAULT 0.5,              -- FSFM-style score (drives TTL/retention)
    reviewed_at  TIMESTAMPTZ DEFAULT now(),
    created_at   TIMESTAMPTZ DEFAULT now(),
    deleted_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS documents_subject_idx ON documents (subject);

-- Nodes: knowledge-graph entities extracted from documents (LLM-extracted, coreference-merged).
-- UNIQUE(name) gives deterministic dedup via INSERT .. ON CONFLICT (fixes the prior custom-schema bug).
CREATE TABLE IF NOT EXISTS nodes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         STRING NOT NULL,
    type         STRING,
    description  STRING,
    embedding    VECTOR(384),                     -- fastembed bge-small-en-v1.5
    weight       FLOAT8 DEFAULT 0.5,              -- reversible demote: 0.05 deep .. 0.5 neutral
    doc_ids      UUID[] DEFAULT ARRAY[]::UUID[],  -- provenance: source documents
    subjects     STRING[] DEFAULT ARRAY[]::STRING[], -- subjects whose docs produced this node
    created_at   TIMESTAMPTZ DEFAULT now(),
    deleted_at   TIMESTAMPTZ,
    UNIQUE (name)
);
CREATE VECTOR INDEX IF NOT EXISTS nodes_embedding_idx ON nodes (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS nodes_deleted_idx ON nodes (deleted_at);

-- Edges: relationships between nodes (the graph). doc_ids = provenance.
CREATE TABLE IF NOT EXISTS edges (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID NOT NULL,
    target_id     UUID NOT NULL,
    relationship  STRING,
    description   STRING,
    doc_ids       UUID[] DEFAULT ARRAY[]::UUID[],
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS edges_source_idx ON edges (source_id);
CREATE INDEX IF NOT EXISTS edges_target_idx ON edges (target_id);

-- Per-subject data-encryption keys. Erasure DESTROYS wrapped_dek => residual ciphertext
-- (in MVCC history, backups, S3) becomes cryptographically unrecoverable (Ghost-Vectors mitigation).
CREATE TABLE IF NOT EXISTS subject_keys (
    subject      STRING PRIMARY KEY,
    wrapped_dek  BYTES,                            -- DEK wrapped (AES-GCM) by the root key
    created_at   TIMESTAMPTZ DEFAULT now(),
    destroyed_at TIMESTAMPTZ
);

-- Erasure audit log + certificate registry (mirrored to object-locked S3).
CREATE TABLE IF NOT EXISTS erasure_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject           STRING,
    t_before          DECIMAL,                     -- cluster_logical_timestamp() pre-delete (AOST anchor)
    docs_removed      INT DEFAULT 0,
    nodes_removed     INT DEFAULT 0,
    edges_removed     INT DEFAULT 0,
    nodes_invalidated INT DEFAULT 0,
    cert_sha256       STRING,
    cert_s3_key       STRING,
    cert_json         JSONB,
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- Memory timeline: ingest / forget / demote / review events for the UI.
CREATE TABLE IF NOT EXISTS timeline (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind       STRING,
    subject    STRING,
    detail     STRING,
    created_at TIMESTAMPTZ DEFAULT now()
);
