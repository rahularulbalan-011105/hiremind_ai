-- ============================================================
-- Dev-only: seed a handful of jobs (no embeddings, no required_skills).
-- The cleaner way is to use POST /api/v1/jobs from the test harness,
-- which also generates the JD embedding. This script is a fallback for
-- when you just need rows quickly.
--
-- Run (PowerShell):
--   Get-Content scripts\seed_jobs.sql | docker exec -i hrms_ai_db psql -U hrms_ai -d hrms_ai
-- ============================================================

INSERT INTO jobs (title, description, company, location, employment_type, metadata)
VALUES
  (
    'Senior Backend Engineer (Python)',
    'Own our async data pipeline. FastAPI + Celery + Postgres. Embeddings & vector search a plus.',
    'Acme',
    'Bengaluru / Remote',
    'full_time',
    jsonb_build_object(
      'required_skills', jsonb_build_array('python','fastapi','postgresql','celery','aws'),
      'required_years_experience', 5
    )
  ),
  (
    'Frontend Engineer (React)',
    'Build the recruiter experience. React, TypeScript, Next.js, design-system thinking.',
    'Acme',
    'Hyderabad',
    'full_time',
    jsonb_build_object(
      'required_skills', jsonb_build_array('react','typescript','next.js','css'),
      'required_years_experience', 3
    )
  ),
  (
    'ML Engineer — Ranking',
    'Train and ship ranking models. XGBoost / LightGBM, SHAP, feature stores, model registry.',
    'Acme',
    'Remote',
    'full_time',
    jsonb_build_object(
      'required_skills', jsonb_build_array('python','xgboost','shap','scikit-learn','sql'),
      'required_years_experience', 4
    )
  )
RETURNING id, title;

-- NOTE: jobs inserted this way have no `job_embeddings` row yet, so
-- /match/score will return 404 ("Job ... has no JD embedding"). To fix:
-- either re-create via POST /api/v1/jobs, or POST /api/v1/embeddings/generate
-- with store_as={"kind":"job","id":"<job_id>"}.
