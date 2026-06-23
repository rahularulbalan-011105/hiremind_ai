# CLAUDE.md — AI HRMS Platform

This file is the source of truth for AI assistants (Claude Code) working in this repo. Read it before making any architectural or implementation decisions.

---

## 1. Project Overview

An **AI-powered recruitment platform**. This repository contains **only the AI subsystem** of a larger HRMS product. The AI subsystem is responsible for:

- Parsing resumes into structured candidate profiles
- Semantic candidate ↔ job matching
- Intelligent candidate ranking
- Fake profile detection
- Duplicate job detection
- Ghost job detection
- Hiring probability prediction
- Semantic vector search

**Architecture style:** enterprise-grade, modular, microservice-oriented, async, API-first, production-ready.

---

## 2. Strict Scope — 8 AI Modules Only

The repo implements **exactly these 8 modules** — nothing more.

| # | Module | Purpose | Status |
|---|---|---|---|
| 1 | Resume Parser | PDF/DOCX → structured candidate JSON (with OCR fallback) | ✅ shipped |
| 2 | Embeddings & Vector Store | Generate + store + search resume/JD embeddings | ✅ shipped |
| 3 | AI Match Engine | Semantic candidate ↔ job match score + reasoning | ✅ shipped (6 dimensions + recruiter fan-out) |
| 4 | Candidate Ranker | Multi-factor ranked candidate list per job | ✅ shipped (with side-by-side compare) |
| 5 | Fake Profile Detector | Trust score + anomaly reasons for candidates | ✅ shipped (5 signals + GitHub cross-check) |
| 6 | Duplicate Detector | Detect duplicate job postings | ✅ shipped |
| 7 | Ghost Job Detector | Detect inactive/fraudulent job postings | ✅ shipped |
| 8 | Hiring Probability Predictor | ML-based hire likelihood with SHAP explainability | ✅ shipped (XGBoost + rules fallback) |

**All 8 modules are feature-complete.** Phase 9 (hardening — Prometheus metrics, rate limits, k8s manifests, load tests) is the only remaining phase from the original plan.

### Hard guardrails — DO NOT

- Do **not** implement a production frontend. A **minimal Next.js test harness** lives under `frontend/` for the sole purpose of exercising AI endpoints during development — it is **not** a product UI and must not grow into one (no auth, no styling system, no state management beyond local React state, no business logic).
- Do **not** implement unrelated HRMS modules (payroll, attendance, leave, performance, etc.).
- Do **not** add AI features outside the 8 listed above (no chatbots, interview bots, sentiment analysis, JD generators, etc.).
- Do **not** introduce new ML/AI libraries beyond the mandated stack without explicit approval.

If a request implies scope creep, flag it and stop.

---

## 3. Mandatory Tech Stack

| Layer | Tech | Status |
|---|---|---|
| Language | Python 3.11 | installed |
| API framework | FastAPI + Uvicorn | installed |
| Async tasks | Celery + Redis | wired (only `resume_parsing` queue is used today) |
| Primary DB | PostgreSQL 16 | via Docker |
| Vector store | pgvector (HNSW cosine index, 768-d) | installed |
| LLM | **Grok or Groq** (OpenAI-compatible), selectable via `LLM_BACKEND` | installed — Groq is the default |
| Classical ML | scikit-learn, XGBoost | installed |
| Explainability | XGBoost native `pred_contribs` (real SHAP values) | installed |
| Embeddings | sentence-transformers (`all-mpnet-base-v2`) | installed |
| OCR | Tesseract via pytesseract (lazy-loaded; PaddleOCR adapter stubbed) | installed |
| Fuzzy matching | RapidFuzz (used by Duplicate Detector + Match Engine) | installed |
| HTTP client | httpx (used by LLM wrapper + GitHub checker) | installed |
| Resilience | tenacity (LLM retries with exponential backoff) | installed |
| Logging | structlog (JSON output, single config in `app/core/logging.py`) | installed |
| Settings | pydantic-settings (single `Settings` object) | installed |
| Resume parsing | pypdf + python-docx | installed |
| Model serialization | joblib + XGBoost native JSON format | installed |

**Vector store abstraction is mandatory.** All vector reads/writes go through a `VectorStore` interface; pgvector is one implementation, Pinecone will be another later.

**LLM abstraction is mandatory.** All LLM calls go through `app/llm/openai_compatible.py` (OpenAI-compatible chat-completions client used by both Grok and Groq) or the `mock` backend (deterministic fake parser for dev without API keys). Pick via `LLM_BACKEND=grok|groq|mock`.

---

## 4. Folder Structure (as built)

```
hrms_ai/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── routers/             # one router per module + helpers
│   │       │   ├── candidates.py    # preferences GET/PUT
│   │       │   ├── duplicate_jobs.py
│   │       │   ├── embeddings.py
│   │       │   ├── fake_profile.py
│   │       │   ├── ghost_jobs.py
│   │       │   ├── health.py
│   │       │   ├── hiring_predictor.py
│   │       │   ├── jobs.py          # create + list + get
│   │       │   ├── match.py         # single-pair + by-job fan-out
│   │       │   ├── ranker.py        # rank + compare
│   │       │   ├── resumes.py
│   │       │   └── vector_search.py
│   │       └── deps.py
│   ├── core/                        # config (pydantic-settings), structlog, typed exceptions
│   ├── db/
│   │   ├── models/                  # one file per table (SQLAlchemy 2.x typed)
│   │   ├── repositories/            # one file per aggregate
│   │   └── session.py
│   ├── schemas/                     # Pydantic DTOs, one file per module
│   ├── services/                    # business logic — one package per module
│   │   ├── duplicate_jobs/
│   │   ├── embeddings/
│   │   ├── fake_profile/            # signals.py + github.py + service.py
│   │   ├── ghost_jobs/
│   │   ├── hiring_predictor/        # features + rules + xgboost + registry + service
│   │   ├── jobs/                    # create + JD embed
│   │   ├── match_engine/            # scorer (pure math) + service (orchestrator)
│   │   ├── ranker/                  # composes 3 + 5 + 8
│   │   └── resume_parser/           # text_extract + ocr + service
│   ├── vector_store/                # base + pgvector + factory (Pinecone stubbed)
│   ├── llm/                         # base + openai_compatible + mock + factory + prompts
│   ├── workers/                     # Celery app + tasks/resume_parser.py
│   └── main.py                      # FastAPI entry, lifespan, CORS, exception handler
├── scripts/
│   ├── migrations/                  # one-shot SQL migrations (idempotent)
│   ├── seed_candidates.sql          # dev test data
│   ├── seed_jobs.sql                # dev test data
│   ├── seed_hiring_outcomes.py      # synthetic outcomes for training Module 8
│   └── train_model.py               # XGBoost training pipeline → model registry
├── db/
│   └── init/                        # 01_extensions, 02_schema, 03_indexes
│                                    # auto-run by Postgres container on first boot
├── artifacts/                       # gitignored — uploaded resumes + trained models
│   ├── uploads/                     # PDF/DOCX from resume parser
│   └── models/<version>/            # XGBoost model.json + metadata.json
├── frontend/                        # Next.js test harness (see §14)
├── docker-compose.yml               # Postgres+pgvector + Redis
├── .env.example                     # template; .env is gitignored
├── .gitignore
├── pyproject.toml
└── README.md (not present yet)
```

**Notes vs original plan:**
- `app/db/migrations/` (Alembic) was **deferred** — we use idempotent SQL in `scripts/migrations/` instead. Alembic can be bootstrapped when complex schema changes start.
- `app/ml/` was **folded into `app/services/hiring_predictor/`** — training pipeline lives in `scripts/train_model.py`.
- `app/utils/` is **empty** — no shared utilities needed yet.
- `tests/` is **not yet populated** — unit-test stubs deferred to hardening phase.
- `deploy/` is **not yet populated** — Dockerfile + k8s manifests deferred to hardening phase.

Service boundaries:
- `api/` is thin — only validation + delegation to `services/`.
- `services/` holds all business logic; no FastAPI imports.
- `db/repositories/` is the only layer that touches the DB.
- `workers/` import services; services never import workers.
- `llm/` is the only layer that makes HTTP calls to an LLM provider.

---

## 5. Module Specifications

### 5.1 Resume Parser ✅

**Flow:** Upload → text extract → OCR fallback → LLM prompt → JSON schema validation → persist candidate → generate embedding inline.

**Extract:** name, email, phone, headline, location, skills, education, experience, certifications, languages.

**Implemented:**
- Upload returns `202 Accepted` + `parse_job_id`; parsing runs async via Celery on the `resume_parsing` queue.
- OCR is **lazy** — Tesseract is loaded only if the PDF appears image-based (extracted text < 200 chars). PaddleOCR adapter exists but is not pip-installed.
- LLM response validated against `ParsedResume` Pydantic model; on `ValidationError`, retries **once** with a stricter prompt that includes the full schema.
- Embedding is generated synchronously **inside the Celery task** after parse succeeds (not as a separate enqueued job).
- Status tracked in `parse_jobs` table — poll via `GET /api/v1/resumes/parse-jobs/{id}`.

### 5.2 Embeddings & Vector Store ✅

**Implemented:**
- `sentence-transformers/all-mpnet-base-v2` loaded once at FastAPI startup; held as a singleton on `app.state.embedding_service`.
- Embeddings stored in pgvector with `vector(768)` columns + **HNSW cosine index** (`m=16, ef_construction=64`) on both `resume_embeddings` and `job_embeddings`.
- Service layer: `EmbeddingService.embed()` + `EmbeddingService.store(kind, entity_id)` writes via `VectorStore.upsert_resume`/`upsert_job`.
- `VectorStore` interface — `PgVectorStore` is the only implementation; Pinecone is stubbed in the factory with a `DependencyError`.
- `POST /api/v1/vector-search/candidates` does top-K cosine; filter fields (`location`, `min_experience_years`) are accepted by the schema but **not pushed to SQL yet** — listed in `ignored_filters` of the response.

### 5.3 AI Match Engine ✅

**Six sub-scores** combined into one composite — extended beyond the original 3-dimensional spec at user request:

| # | Sub-score | Default weight | Notes |
|---|---|---|---|
| 1 | Semantic | 0.25 | cosine of resume vs JD embedding remapped to [0, 100] |
| 2 | Skill overlap | 0.25 | uses `required_skills: [{skill, min_years}]` — candidate must meet `min_years` per skill |
| 3 | Experience | 0.15 | candidate years vs `required_years_experience` (capped at 120%) |
| 4 | **Location** | 0.10 | alias-aware (Bengaluru ≡ Bangalore), remote-aware, candidate preferences override |
| 5 | **Notice period** | 0.10 | candidate's `available_notice_days` vs job's `notice_period_days_max` |
| 6 | **Salary** | 0.15 | range-overlap rule; under-budget candidates score 100, over-budget scales down |

**Two endpoints:**
- `POST /api/v1/match/score` — single pair `(candidate_id, job_id)`. Scoring is deterministic math; **LLM call** is used only for `reasoning_bullets` (rule-based fallback if LLM fails). Cached in `match_scores` table.
- `POST /api/v1/match/by-job` — fan-out across all candidates with embeddings for one job. **No LLM per row** (would burn rate limits). Each row also carries `fake_profile_risk` and pairwise `possible_duplicates` within the result set.

**Example output:**
```json
{
  "match_score": 76,
  "subscores": {"semantic": 78, "skill_overlap": 100, "experience": 100,
                "location": 100, "notice_period": 100, "salary": 100},
  "reasoning": ["Strong Python overlap on core requirements", "..."],
  "weights_used": {...},
  "cached": false
}
```

### 5.4 Candidate Ranker ✅

**Composes outputs of Modules 3 + 5 + 8 + raw experience seniority into one final 0–100 score.**

| Input | Source | Default weight |
|---|---|---|
| Match score | Module 3 (cached `match_scores` row, computed inline if missing) | **0.45** |
| Hiring probability × 100 | Module 8 (cached `hiring_predictions`, computed inline if missing) | **0.30** |
| Trust score | Module 5 (cached `fake_profile_scores`, defaults to 100 if not scored) | **0.15** |
| Experience seniority | `min(years/15, 1) × 100` | **0.10** |

Weights are overridable per request and auto-normalized to sum to 1.

**Two endpoints:**
- `POST /api/v1/rank/candidates` — ranks all candidates against one job, returns sorted top-K with full component breakdown
- `POST /api/v1/rank/compare` — side-by-side comparison of 1–20 hand-picked candidates against one job (preserves input order)

Bulk-loads from cache to keep latency low. Each row also carries `fake_profile_risk` badge and `hiring_model_type` (`xgboost` or `rules`).

### 5.5 Fake Profile Detector ✅

**5 internal signals + GitHub cross-check.** Returns rich payload (every signal listed whether fired or not, plus reasoning bullets + GitHub block) so the frontend page can render a full explanation.

| Signal | Penalty (each) | Cap |
|---|---|---|
| Employment gap (≥ 6 months) | −10 | −30 |
| Overlapping full-time roles (> 30 days) | −15 | −30 |
| Duplicate email/phone matches another candidate | −25 | −40 |
| Suspiciously perfect completeness (all optional fields + ≥10 skills) | −5 | −5 |
| Inconsistent timeline (education ends after first job starts) | −20 | −20 |

`trust_score = max(0, 100 − Σ penalties)`. Bucketed into `low / medium / high` at thresholds 70 / 40.

**GitHub cross-check** (`POST /api/v1/fake-profile/score` accepts `github_username` override or extracts from `raw_text`):
- Free public-API path (`GITHUB_TOKEN` optional for 60→5000 req/hr).
- Fetches profile + repo languages; flags fresh accounts (< 90d), zero-repo accounts, skills claimed in resume but absent from any repo.

**Duplicate-candidate detection** is **not** part of this endpoint. It's computed inline in `/match/by-job` only — within the recruiter's ranked result set, never DB-wide (deliberate, for performance + because cross-context duplicates aren't actionable).

**Deliberately deferred:** LinkedIn cross-check (requires Partner Program / paid scrape API), Aadhaar verification (requires UIDAI license or KYC aggregator), Onfido-style identity verification (requires paid SaaS account). These are integration points, not features missing from this module.

Output: `trust_score (0–100)`, `risk_level`, `reasoning_bullets[]`, `score_breakdown[]` (every signal), `github_check{}`.

### 5.6 Duplicate Job Detector ✅

**`POST /api/v1/jobs/duplicate-check`** — three signals combined into one verdict.

| Signal | Source |
|---|---|
| Fuzzy title | RapidFuzz `token_set_ratio` on `jobs.title` (uses `pg_trgm` index) |
| JD embedding cosine | pgvector HNSW pre-filter (top-N by cosine distance) |
| Same company | Case-insensitive match on `jobs.company` |
| Required-skill overlap | Jaccard of `required_skills` sets (reported but not in verdict math) |

**Verdicts:**
- `hard` — same company + (title ≥ 0.90 OR embedding ≥ 0.97)
- `likely` — title ≥ 0.85 AND embedding ≥ 0.92
- `similar` — embedding ≥ 0.90 OR title ≥ 0.85
- Cross-company pairs need both signals strong (deliberate — different companies hiring for the same role aren't duplicates, just market overlap).

**Performance:** HNSW pre-filter narrows ≤ N candidates (default 50) before fuzzy/skills check in Python. Persists clusters to `duplicate_job_clusters` (method `combined`).

### 5.7 Ghost Job Detector ✅

**`POST /api/v1/jobs/ghost-score`** — 5 tiered signals that **add** to ghost_score (higher = more ghost-like).

| Signal | Tier penalties |
|---|---|
| Posting age | > 30d: +10, > 60d: +10, > 120d: +15 (cumulative) |
| Days since last activity | > 30d: +15, > 60d: +15, > 90d: +20 |
| Repost count | ≥ 3: +10, ≥ 5: +10 |
| Zero candidate interaction (after 14d grace) | +10 |
| Stale interaction (> 30d since last `match_scores` row) | +5 |

**Classification:** `active` (< 30), `stale` (30–59), `likely_ghost` (≥ 60). Returned with the full raw signals table (posting_age_days, days_since_last_activity, repost_count, match_scores_count, days_since_last_interaction, job_status) + per-signal breakdown.

Cached in `ghost_job_scores`, but **scores age over time** — `force_recompute: true` skips cache.

### 5.8 Hiring Probability Predictor ✅

**Always-works hybrid:** XGBoost if a trained model exists for `MODEL_VERSION`, else a rules-based predictor.

**11 features** (frozen ordering — `FEATURE_NAMES` in `app/services/hiring_predictor/features.py`):
1. `semantic_score`, `skill_overlap_score`, `experience_score`, `location_score`, `notice_period_score`, `salary_score` — from `match_scores` cache or computed live
2. `trust_score` — from `fake_profile_scores` (defaults to 100 if not scored)
3. `candidate_years` (raw years from experience intervals)
4. `required_years_gap` (`candidate_years - required_years`)
5. `meets_all_required_skills` (binary)
6. `github_verified_skills` (binary — set if GitHub check confirmed any claimed skill)

**Training pipeline:** `python -m scripts.train_model --version v1`
- Loads `hiring_outcomes` rows, builds feature matrix, trains XGBoost `binary:logistic` with AUC early-stopping
- Persists to `artifacts/models/<version>/{model.json, metadata.json}` + writes a row to `ml_models` table
- Logs training metrics (AUC, accuracy, n_train, n_test)

**SHAP:** Uses XGBoost native `pred_contribs` (which is what `shap` uses internally) — real per-feature contributions, no extra inference-time dependency.

**Synthetic seed:** `python -m scripts.seed_hiring_outcomes --target 200` generates plausible hiring outcomes from existing candidate × job pairs so XGBoost has something genuinely to learn (the "true" coefficients differ from the rules predictor weights on purpose).

**Endpoint:** `POST /api/v1/hiring-probability/predict` → `{probability, confidence, model_version, model_type, features_used, shap_explanations, cached}`. Same shape regardless of which predictor served it.

---

## 6. Architecture Requirements

- **Service-oriented:** each module is an isolated service package under `app/services/`.
- **Async-first:** long-running work (parsing, embedding, training, batch scoring) runs through Celery + Redis.
- **Repository pattern:** all DB access via repositories; services depend on repository interfaces.
- **DTO discipline:** Pydantic models for every request/response — no raw dicts across boundaries.
- **API gateway compatible:** all endpoints versioned under `/api/v1/...`, stateless, JWT-ready.
- **Retries:** Celery tasks use exponential backoff; LLM and embedding calls use tenacity with bounded retries.
- **Logging:** structured JSON logging (one logger config in `app/core/logging.py`), correlation IDs propagated from API → worker.
- **Error handling:** typed exceptions per module, mapped to HTTP error responses in a single FastAPI exception handler.
- **Config:** all secrets/URLs via env vars, loaded through a single `Settings` (pydantic-settings) object.

---

## 7. Environment Variables (current)

See `.env.example` for the authoritative list. Summary:

```
# App
APP_ENV=development|staging|production
LOG_LEVEL=INFO

# Postgres (used by docker-compose AND the app)
POSTGRES_DB=hrms_ai
POSTGRES_USER=hrms_ai
POSTGRES_PASSWORD=hrms_ai
POSTGRES_PORT=5432           # 5433 if host has a competing local Postgres
DATABASE_URL=postgresql+psycopg://hrms_ai:hrms_ai@localhost:5432/hrms_ai
PGVECTOR_DIM=768

# Redis / Celery
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# LLM — pick one: mock | grok | groq
LLM_BACKEND=mock
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=2

# Grok (xAI) — keys start with `xai-`
GROK_API_KEY=
GROK_API_BASE=https://api.x.ai/v1
GROK_MODEL=grok-2-latest

# Groq (LPU inference) — keys start with `gsk_`
GROQ_API_KEY=
GROQ_API_BASE=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile

# Embeddings
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2

# GitHub cross-check (Module 5)
GITHUB_TOKEN=                # optional; raises rate limit 60→5000/hr
GITHUB_TIMEOUT_SECONDS=10

# OCR
OCR_ENGINE=tesseract         # or paddle (stubbed; not installed by default)

# Vector store
VECTOR_STORE_BACKEND=pgvector
PINECONE_API_KEY=
PINECONE_INDEX=

# Artifacts + ML
ARTIFACTS_DIR=./artifacts
MODEL_REGISTRY_PATH=./artifacts/models
MODEL_VERSION=v1

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**`.env` is gitignored.** Real secrets belong there; `.env.example` is the safe-to-commit template with empty placeholders.

---

## 8. API Surface (current)

All endpoints accept/return JSON, documented via FastAPI's OpenAPI schema at `/docs`. Each router includes example payloads in its docstring.

### Core module endpoints

| Method | Path | Module |
|---|---|---|
| GET | `/api/v1/health` | Health (DB + embedding model status) |
| POST | `/api/v1/resumes/parse` | Resume Parser (async, returns `parse_job_id`) |
| GET | `/api/v1/resumes/parse-jobs/{parse_job_id}` | Resume Parser (poll) |
| GET | `/api/v1/resumes/{candidate_id}` | Resume Parser (full profile) |
| POST | `/api/v1/embeddings/generate` | Embeddings (text → vector, optionally stored) |
| POST | `/api/v1/vector-search/candidates` | Vector search (top-K cosine) |
| POST | `/api/v1/match/score` | Match Engine (single pair, with LLM reasoning) |
| POST | `/api/v1/match/by-job` | Match Engine fan-out (recruiter view) |
| POST | `/api/v1/rank/candidates` | Ranker (sorted ranked list) |
| POST | `/api/v1/rank/compare` | Ranker (side-by-side compare) |
| POST | `/api/v1/fake-profile/score` | Fake Profile Detector |
| POST | `/api/v1/jobs/duplicate-check` | Duplicate Job Detector |
| POST | `/api/v1/jobs/ghost-score` | Ghost Job Detector |
| POST | `/api/v1/hiring-probability/predict` | Hiring Predictor |

### Supporting endpoints (built to enable the modules above)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/jobs` | Create a job + generate JD embedding |
| GET | `/api/v1/jobs` | List jobs (with optional `status`, `limit`, `offset`) |
| GET | `/api/v1/jobs/{job_id}` | Fetch a single job |
| GET | `/api/v1/candidates/{candidate_id}/preferences` | Read preferences (notice, salary, locations, skill_years) |
| PUT | `/api/v1/candidates/{candidate_id}/preferences` | Replace preferences |

---

## 9. Database & pgvector Schema (as built)

**Tables (15 total):**

| Table | Purpose | Module |
|---|---|---|
| `candidates` | parsed profile + `preferences` JSONB | 1, 4, all |
| `candidate_experience` | per-role intervals | 1, 5 |
| `candidate_education` | degrees + dates | 1, 5 |
| `candidate_skills` | skill names (+ optional `years`, `proficiency`) | 1, 3 |
| `candidate_certifications` | certs | 1 |
| `candidate_languages` | languages + proficiency | 1 |
| `parse_jobs` | async resume parse status | 1 |
| `jobs` | postings + `metadata` JSONB (required_skills, notice, salary) | 3a |
| `resume_embeddings` | `vector(768)` + model + ts; HNSW cosine index | 2 |
| `job_embeddings` | `vector(768)` + model + ts; HNSW cosine index | 2 |
| `match_scores` | composite + reasoning JSONB (sub-scores + bullets + weights) | 3 |
| `fake_profile_scores` | trust + risk + anomalies JSONB (breakdown + bullets + github_check) | 5 |
| `duplicate_job_clusters` | one row per pair × method | 6 |
| `ghost_job_scores` | score + classification + signals JSONB | 7 |
| `hiring_predictions` | probability + confidence + shap JSONB | 8 |
| `hiring_outcomes` | training labels (hired / rejected / withdrawn / no_show) | 8 (training) |
| `ml_models` | model registry mirror — `name`, `version`, `artifact_path`, `metrics`, `is_active` | 8 |

**Indexes:**
- pgvector **HNSW cosine** on `resume_embeddings.embedding` and `job_embeddings.embedding` (`m=16, ef_construction=64`).
- **pg_trgm GIN** on `jobs.title` (fuzzy title search for Module 6).
- BTREE on foreign keys + hot lookup paths.
- GIN on JSONB columns where used for predicate filtering.

**Migration strategy (current):**
- `db/init/*.sql` runs on first container boot only — extensions, all tables, all indexes.
- Ongoing schema changes go through `scripts/migrations/NNN_*.sql` — **idempotent SQL** the user runs manually (e.g., `001_add_candidate_preferences.sql`).
- **Alembic is deferred** until schema changes get complex enough to need a proper migration graph.

---

## 10. Celery Worker Design (current vs planned)

**Planned queues** (CLAUDE.md original spec):
- `resume_parsing` · `embeddings` · `scoring` · `ml_inference` · `training`

**Built today:** only **`resume_parsing`** — it's the only module with genuinely slow work (OCR + LLM call + persist + embed). The other modules are sub-100ms synchronous calls, so Celery wasn't justified yet.

- API publishes via `celery_app.send_task("...", queue="resume_parsing")` (explicit broker is Redis; this avoids the `kombu` AMQP-default fallback gotcha).
- Worker launched via `celery -A app.workers.celery_app worker -Q resume_parsing --pool=solo` (Windows; `prefork` on Linux/Mac).
- Worker initializes its own `EmbeddingService` singleton per process (model is loaded once per worker on first task).

**When to add the other queues:**
- `scoring` — when batch re-scoring of cached results becomes a thing (e.g., re-rank everyone after weight tuning).
- `ml_inference` — when prediction load justifies offloading from API.
- `training` — when retraining becomes scheduled / periodic rather than manual via `scripts/train_model.py`.

Each module exposes its tasks under `app/workers/tasks/<module>.py`. Tasks import services, never the reverse.

---

## 11. Deployment & Scaling

- **Containerization:** one Dockerfile, multi-stage; same image runs API or worker via entrypoint flag.
- **Orchestration:** Kubernetes-friendly; horizontal scaling per worker queue.
- **Observability:** structured logs → stdout; Prometheus metrics endpoint on API; OpenTelemetry tracing-ready.
- **Scaling levers:**
  - API: replicas behind gateway
  - Workers: scale per queue based on backlog
  - pgvector: ANN index tuning, read replicas; migrate to Pinecone behind `VectorStore` interface when scale demands
  - LLM: per-tenant rate limits, response cache for repeat JD/resume pairs

---

## 12. Implementation Plan (phase status)

| Phase | Module | Status |
|---|---|---|
| 1 | **Scaffolding** — folder structure, settings, logging, DB session, Celery app, Docker | ✅ done |
| 2 | **Embeddings & Vector Store** | ✅ done |
| 3 | **Resume Parser** — upload → parse → store → embed end-to-end | ✅ done |
| 4 | **AI Match Engine** — embeddings + LLM reasoning (Grok or Groq) | ✅ done — extended to 6 dimensions |
| 5 | **Fake Profile Detector** — 5 rules + GitHub cross-check | ✅ done |
| 6 | **Duplicate Detector** | ✅ done |
| 6 | **Ghost Job Detector** | ✅ done |
| 7 | **Hiring Probability Predictor** — training pipeline + inference API + SHAP | ✅ done |
| 8 | **Candidate Ranker** — composes outputs of 3, 5, 7 | ✅ done |
| 9 | **Hardening** — retries, rate limits, metrics, load tests, k8s manifests | ⏳ remaining |

Each shipped phase includes: Pydantic schemas, repository methods, service module, router, example payloads in router docstrings, frontend test page. **Unit tests are deferred to Phase 9 hardening.**

---

## 13. Local Dev Environment

The full local stack runs via Docker Compose. **You do not need Postgres installed on the host.**

```bash
docker compose up -d        # start postgres (with pgvector) + redis
docker compose logs -f db   # tail DB logs
docker compose down         # stop; add -v to wipe data
```

**Services:**
- `db` — `pgvector/pgvector:pg16` image, port `5432`, db `hrms_ai`, user/pass from `.env`
- `redis` — `redis:7-alpine`, port `6379`

**First-boot init:** every `.sql` file in `db/init/` runs in alphabetical order the first time the `db` volume is created. To re-run them, `docker compose down -v` then `up -d`.

Schema lifecycle:
- `db/init/*.sql` is for first-boot bootstrap only (extensions + initial schema).
- Ongoing schema changes go through **Alembic migrations** under `app/db/migrations/`.

---

## 14. Next.js Test Harness (`frontend/`)

A throwaway dev tool. **Not part of the product.** Its only job is to let a human poke the FastAPI endpoints from a browser.

**Allowed:**
- Next.js (App Router) + TypeScript
- Plain CSS (no Tailwind, no UI kit)
- Local React state only
- One page per AI endpoint: a form for the request, a `<pre>` for the response

**Forbidden** (would turn this into a product UI):
- Authentication / sessions
- Global state stores (Redux, Zustand, etc.)
- Component libraries (MUI, shadcn, Chakra, etc.)
- Server-side rendering of AI data, Next.js API routes that wrap the FastAPI
- Caching, optimistic updates, routing logic beyond simple `<Link>`s

The harness calls FastAPI directly via `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`). CORS must be permissive in `APP_ENV=development`.

Run it:
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

If the test harness ever needs a feature beyond the "allowed" list, stop and confirm with the user — that's a signal we're building the wrong thing here.

---

## 15. Conventions for Claude

- Prefer editing existing files over creating new ones.
- Never add a module or library outside the scope in §2 / §3 without asking.
- Every new endpoint needs: Pydantic request + response schema, service function, repository method (if it touches DB), example payload in the router docstring, and (when Phase 9 lands) a unit-test stub under `tests/`.
- Long-running work must go through Celery, not block the API.
- Vector reads/writes go through `VectorStore`, never raw SQL in services.
- LLM calls go through the `app/llm/` wrapper (retries + logging + prompt registry), never direct HTTP from services.
- Never name a method `list`, `dict`, `set`, `id`, `type`, etc. inside a class body — Python's class-scope lookup will shadow the builtin in other methods' annotations and cause confusing `TypeError: 'function' object is not subscriptable` on import.
- All new env vars get added to `.env.example` in the same PR. `.env` is gitignored.
- Schema changes go in a new `scripts/migrations/NNN_*.sql` (idempotent) AND update `db/init/02_schema.sql` so fresh setups also get them.

---

## 16. Implementation Status & Deviations from Spec

### What's complete
All 8 AI modules + the supporting endpoints (jobs CRUD, candidate preferences). The system is feature-complete per the original CLAUDE.md spec, with several extensions made at user request during the build.

### Beyond-spec extensions actually shipped
| Where | What | Why |
|---|---|---|
| Module 3 | Match scoring extended from 3 to **6 dimensions** (added location, notice, salary) | Recruiter request — these are real hiring constraints |
| Module 3 | `POST /match/by-job` fan-out for recruiters | Recruiter wants ranked candidates per job, not just pair scoring |
| Module 4 | `POST /rank/compare` side-by-side endpoint | Spec called for it; built it as a separate route |
| Module 5 | GitHub cross-check (public API, real verification) | User asked for external verifiers; this is the one that's legally + technically feasible without paid integrations |
| Module 5 | Pairwise candidate duplicate detection in `/match/by-job` | Recruiters need to spot redundant resubmissions |
| Module 8 | Rules-based predictor as XGBoost fallback | The endpoint never hard-fails even without a trained model |
| Module 8 | Synthetic outcome generator for training-from-cold-start | Real `hiring_outcomes` don't exist yet; XGBoost needs labels |
| Infra | Groq added as a 2nd OpenAI-compatible LLM backend | Cheaper / faster than Grok for dev; same wrapper |
| Infra | `mock` LLM backend (deterministic fake parser) | Lets dev run end-to-end without any API key |
| Infra | Candidate preferences (`PUT /candidates/{id}/preferences`) | Resumes don't carry notice/salary/skill_years; the new match dimensions need this data |

### Deliberately deferred (NOT bugs)
| Item | Reason | When to revisit |
|---|---|---|
| Alembic migrations | Idempotent SQL in `scripts/migrations/` suffices today | When schema changes get complex (multi-table refactor, data backfills) |
| Unit tests | Module velocity prioritized; the test harness gives equivalent feedback | Phase 9 hardening |
| LinkedIn cross-check | No legal API path; requires Partner Program or paid scraper | When a paid Proxycurl-style account is provisioned |
| Aadhaar verification | Requires UIDAI license OR KYC aggregator (Karza/Digio/Signzy) + consent flow + DPDP compliance | If/when the platform handles onboarding (not screening) |
| Onfido / Persona / Veriff | Paid SaaS; better fit for post-offer onboarding | Same as Aadhaar |
| Vector-search SQL filters (`location`, `min_experience_years`) | Schema accepts them; they're `ignored_filters` in the response | Trivial add — needs JOIN through `candidate_experience` / `candidates.location` |
| Filter pushdown on match-by-job | Same gap as vector-search filters | Same |
| PaddleOCR | Tesseract is the lighter, more reliable path on Windows | If accuracy on image-based PDFs becomes a blocker |
| Frontend rate-limiting / auth | Test harness — out of scope per §14 | Never (this stays a dev tool) |
| Pinecone backend | `VectorStore` interface ready; pgvector handles current scale | When candidate count exceeds ~1M or read QPS demands it |
| Per-tenant LLM rate limits / response cache | No multi-tenant traffic yet | Phase 9 hardening |
| Prometheus metrics + OpenTelemetry tracing | Logs cover dev needs | Phase 9 hardening |
| Dockerfile + k8s manifests for the API/worker | Local dev uses uvicorn + native Celery | Phase 9 hardening |

### What's left for Phase 9 (hardening)
- Unit + integration test suite (the harness has been doing the work)
- Prometheus `/metrics` endpoint, structured logs already-JSON
- OpenTelemetry tracing context (correlation IDs from API → worker)
- Per-route rate limits + per-tenant LLM budget caps
- Multi-stage Dockerfile + k8s manifests for API and worker
- Load tests (k6 or locust) on `/match/by-job` and `/rank/candidates` — the heaviest endpoints
- Alembic bootstrap + migrate `scripts/migrations/*.sql` history into it
- LLM response cache (keyed by resume_text hash + JD hash) to skip duplicate Groq calls

### Known quirks encountered during the build (recorded for future Claude)
- **Windows + Postgres:** if `postgres.exe` is already running on `:5432`, the docker container binds but loopback reaches the wrong one — symptom is `password authentication failed for user "hrms_ai"`. Fix: stop the local service OR change `POSTGRES_PORT` to 5433 and update `DATABASE_URL`.
- **Celery on Windows:** `--pool=solo` is the working pool. `prefork` (default on Mac/Linux) hangs on Windows.
- **Celery broker drift:** if the API doesn't import `app.workers.celery_app`, `kombu` falls back to AMQP defaults and you get `ConnectionRefusedError [WinError 10061]`. Fix lives in `app/main.py` (imports the module) **and** `app/api/v1/routers/resumes.py` (uses `celery_app.send_task` explicitly rather than `task.delay`).
- **EmailStr in Pydantic:** requires `pydantic[email]` extra. We use plain `str` for the candidate email field instead — LLM-parsed emails often have weird formatting that strict RFC validation rejects.
