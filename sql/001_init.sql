-- Chat DBV - esquema inicial (PoC). Idêntico ao que o backend Java/Spring AI usará depois.
-- Dimensão 768 = gemini-embedding-001 com output_dimensionality=768 (vetores normalizados).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS manuais (
    id          BIGSERIAL PRIMARY KEY,
    titulo      TEXT        NOT NULL,
    arquivo     TEXT        NOT NULL UNIQUE,   -- caminho relativo em data/manuais
    categoria   TEXT        NOT NULL DEFAULT 'GERAL',
    sha256      TEXT        NOT NULL,          -- permite ingestão idempotente
    paginas     INTEGER,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          BIGSERIAL PRIMARY KEY,
    manual_id   BIGINT      NOT NULL REFERENCES manuais(id) ON DELETE CASCADE,
    categoria   TEXT        NOT NULL,          -- denormalizada para filtro rápido
    pagina      INTEGER     NOT NULL,
    ordem       INTEGER     NOT NULL,          -- posição do chunk dentro do manual
    texto       TEXT        NOT NULL,
    embedding   vector(768) NOT NULL,
    -- Full-Text Search em português (siglas/códigos exatos que a busca semântica perde)
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', texto)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_categoria_idx ON chunks (categoria);
CREATE INDEX IF NOT EXISTS chunks_manual_idx ON chunks (manual_id);

-- Feedback das respostas (👍/👎) para avaliar a PoC
CREATE TABLE IF NOT EXISTS feedback (
    id          BIGSERIAL PRIMARY KEY,
    pergunta    TEXT        NOT NULL,
    resposta    TEXT        NOT NULL,
    positivo    BOOLEAN     NOT NULL,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Histórico de conversas vinculado ao navegador (device_id sem login)
CREATE TABLE IF NOT EXISTS conversas (
    id                  TEXT        PRIMARY KEY,
    device_id           TEXT        NOT NULL,
    titulo              TEXT        NOT NULL,
    modo                TEXT        NOT NULL DEFAULT 'consulta',
    categoria           TEXT        NOT NULL DEFAULT 'TODAS',
    last_interaction_id TEXT,
    mensagens_json      TEXT        NOT NULL DEFAULT '[]',
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversas_device_idx ON conversas (device_id, atualizado_em DESC);
