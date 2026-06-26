-- ============================================================
-- Extensions required by the HRMS AI subsystem.
-- Runs once on first boot of the Postgres container.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- fuzzy title matching for duplicate detector
