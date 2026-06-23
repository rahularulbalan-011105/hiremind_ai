-- ============================================================
-- One-shot migration: add the `preferences` JSONB column to candidates.
-- Run via:
--   Get-Content scripts\migrations\001_add_candidate_preferences.sql `
--     | docker exec -i hrms_ai_db psql -U hrms_ai -d hrms_ai
--
-- Idempotent: re-running is safe.
-- ============================================================

ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}'::jsonb;
