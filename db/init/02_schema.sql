-- ============================================================
-- HRMS AI — initial schema.
-- Bootstrap only. Ongoing changes go through Alembic migrations.
-- Embedding dimension assumes sentence-transformers/all-mpnet-base-v2 (768).
-- ============================================================

-- ---------- Candidates ----------

CREATE TABLE candidates (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       TEXT         NOT NULL,
    email           TEXT         UNIQUE,
    phone           TEXT,
    headline        TEXT,
    location        TEXT,
    raw_resume_url  TEXT,
    raw_text        TEXT,
    source          TEXT,
    preferences     JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE candidate_experience (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    company       TEXT         NOT NULL,
    title         TEXT,
    start_date    DATE,
    end_date      DATE,
    is_current    BOOLEAN      NOT NULL DEFAULT FALSE,
    description   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE candidate_education (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    institution   TEXT         NOT NULL,
    degree        TEXT,
    field         TEXT,
    start_date    DATE,
    end_date      DATE,
    grade         TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE candidate_skills (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    skill         TEXT         NOT NULL,
    proficiency   TEXT,
    years         NUMERIC(4,1),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, skill)
);

CREATE TABLE candidate_certifications (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    name          TEXT         NOT NULL,
    issuer        TEXT,
    issued_date   DATE,
    expires_date  DATE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE candidate_languages (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    language      TEXT         NOT NULL,
    proficiency   TEXT,
    UNIQUE (candidate_id, language)
);

-- ---------- Resume parse jobs (async tracking) ----------

CREATE TABLE parse_jobs (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         REFERENCES candidates(id) ON DELETE SET NULL,
    status        TEXT         NOT NULL CHECK (status IN ('queued','running','succeeded','failed')),
    source_url    TEXT,
    error         TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------- Jobs ----------

CREATE TABLE jobs (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    title             TEXT         NOT NULL,
    description       TEXT         NOT NULL,
    company           TEXT,
    location          TEXT,
    employment_type   TEXT,
    recruiter_id      UUID,
    status            TEXT         NOT NULL DEFAULT 'active'
                                   CHECK (status IN ('active','paused','closed','archived')),
    posted_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_activity_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ,
    repost_count      INTEGER      NOT NULL DEFAULT 0,
    metadata          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------- Embeddings (pgvector) ----------
-- NOTE: dim is hard-coded to 768. If EMBEDDING_MODEL changes, write an Alembic
-- migration that creates a new table with the new dim and migrates data.

CREATE TABLE resume_embeddings (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
    embedding     vector(768)  NOT NULL,
    model         TEXT         NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE job_embeddings (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID         NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    embedding   vector(768)  NOT NULL,
    model       TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------- Match scores ----------

CREATE TABLE match_scores (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    job_id        UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    score         NUMERIC(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    reasoning     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    computed_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, job_id)
);

-- ---------- Hiring probability predictions ----------

CREATE TABLE hiring_predictions (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id   UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    job_id         UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    probability    NUMERIC(5,4) NOT NULL CHECK (probability BETWEEN 0 AND 1),
    confidence     NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    shap           JSONB        NOT NULL DEFAULT '[]'::jsonb,
    model_version  TEXT         NOT NULL,
    computed_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, job_id, model_version)
);

-- ---------- Hiring outcomes (training labels) ----------

CREATE TABLE hiring_outcomes (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    job_id        UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    outcome       TEXT         NOT NULL CHECK (outcome IN ('hired','rejected','withdrawn','no_show')),
    decided_at    TIMESTAMPTZ  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, job_id)
);

-- ---------- Fake profile detector ----------

CREATE TABLE fake_profile_scores (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID         NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
    trust_score   NUMERIC(5,2) NOT NULL CHECK (trust_score BETWEEN 0 AND 100),
    risk_level    TEXT         NOT NULL CHECK (risk_level IN ('low','medium','high')),
    anomalies     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    computed_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------- Duplicate job clusters ----------

CREATE TABLE duplicate_job_clusters (
    id                    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    duplicate_of_job_id   UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    similarity            NUMERIC(5,4) NOT NULL CHECK (similarity BETWEEN 0 AND 1),
    method                TEXT         NOT NULL CHECK (method IN ('fuzzy_title','embedding','combined')),
    computed_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (job_id, duplicate_of_job_id, method),
    CHECK (job_id <> duplicate_of_job_id)
);

-- ---------- Ghost job detector ----------

CREATE TABLE ghost_job_scores (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id               UUID         NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    ghost_score          NUMERIC(5,2) NOT NULL CHECK (ghost_score BETWEEN 0 AND 100),
    risk_classification  TEXT         NOT NULL CHECK (risk_classification IN ('active','stale','likely_ghost')),
    signals              JSONB        NOT NULL DEFAULT '{}'::jsonb,
    computed_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------- ML model registry (for hiring predictor versions) ----------

CREATE TABLE ml_models (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT         NOT NULL,
    version       TEXT         NOT NULL,
    artifact_path TEXT         NOT NULL,
    metrics       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    is_active     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
