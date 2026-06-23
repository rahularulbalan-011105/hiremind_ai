-- ============================================================
-- Dev-only: seed a handful of candidates so vector search has
-- something to return before the Resume Parser module is built.
--
-- Run:
--   docker exec -i hrms_ai_db psql -U hrms_ai -d hrms_ai \
--     -f /dev/stdin < scripts/seed_candidates.sql
--
-- (Windows PowerShell:
--   Get-Content scripts\seed_candidates.sql | docker exec -i hrms_ai_db psql -U hrms_ai -d hrms_ai
-- )
-- ============================================================

INSERT INTO candidates (full_name, email, headline, location) VALUES
  ('Alice Lee',    'alice@example.com', 'Senior Python engineer — FastAPI, pgvector, Celery', 'Bengaluru'),
  ('Bob Chen',     'bob@example.com',   'Frontend engineer — React, TypeScript, Next.js',     'Remote'),
  ('Carol Singh',  'carol@example.com', 'ML engineer — XGBoost, SHAP, sentence-transformers', 'Hyderabad'),
  ('Dinesh Rao',   'dinesh@example.com','DevOps engineer — Kubernetes, Terraform, AWS',       'Pune'),
  ('Eva Martins',  'eva@example.com',   'Data engineer — Airflow, dbt, Snowflake',            'Lisbon')
ON CONFLICT (email) DO NOTHING
RETURNING id, full_name, email;
