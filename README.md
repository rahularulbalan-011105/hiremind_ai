# HRMS AI — Recruitment Intelligence Backend

An AI-powered recruitment subsystem for an HRMS platform. This repo contains **only the AI backend** (FastAPI + Celery + Postgres + pgvector) — no UI, no HR features outside hiring. A small Next.js test harness ships under `frontendv01/` for manually poking endpoints during dev.

> **TL;DR for a new dev:** clone repo → install Python 3.11 → install Tesseract → copy `.env.example` to `.env` → `docker compose up -d` → `pip install -e .` → `uvicorn app.main:app --reload` → open http://localhost:8000/docs.

---

## 1. What this system actually does

Eight AI modules, all shipped and reachable over HTTP:

| # | Module | What it does |
|---|---|---|
| 1 | **Resume Parser** | PDF/DOCX → structured candidate JSON (with OCR fallback for image PDFs) |
| 2 | **Embeddings + Vector Store** | Generates 768-d embeddings (sentence-transformers `all-mpnet-base-v2`), stores in pgvector with HNSW cosine index, supports top-K semantic search |
| 3 | **AI Match Engine** | 6-dimension match score (semantic, skills, experience, location, notice, salary) + LLM reasoning bullets. Has single-pair and recruiter fan-out endpoints |
| 4 | **Candidate Ranker** | Composes Modules 3+5+8 into one ranked list per job. Has side-by-side compare endpoint |
| 5 | **Fake Profile Detector** | 5 internal signals + GitHub cross-check → trust score + risk level + reasoning bullets |
| 6 | **Duplicate Job Detector** | Fuzzy title + JD-embedding cosine + same-company verdict (hard / likely / similar) |
| 7 | **Ghost Job Detector** | 5 tiered signals → active / stale / likely_ghost classification |
| 8 | **Hiring Probability Predictor** | XGBoost (if model trained) or rules-based fallback. Returns probability + SHAP per-feature contributions |

All endpoints under `/api/v1/...`. OpenAPI docs at **`/docs`** (Swagger) and **`/redoc`** when the server is up.

---

## 2. Tech stack

| Layer | Tech | Notes |
|---|---|---|
| Language | **Python 3.11** | Pinned in `pyproject.toml` (`>=3.11,<3.12`) |
| API | FastAPI + Uvicorn | App entry: `app/main.py` |
| Async tasks | Celery + Redis | Only `resume_parsing` queue is used today |
| DB | Postgres 16 + pgvector | Runs in Docker via `docker-compose.yml` |
| Vector store | pgvector (HNSW cosine, 768-d) | Pinecone interface stubbed for later |
| LLM | Grok **or** Groq (OpenAI-compatible) | Switch with `LLM_BACKEND=grok\|groq\|mock`. Default in `.env.example` is `mock` so it runs without keys |
| Embeddings | sentence-transformers `all-mpnet-base-v2` | Loaded once at startup; ~420 MB download on first run |
| Classical ML | scikit-learn + XGBoost | XGBoost native JSON model format + SHAP via `pred_contribs` |
| OCR | Tesseract via `pytesseract` | Lazy-loaded only when a PDF looks image-based (<200 chars extracted) |
| Fuzzy match | RapidFuzz | Used in Duplicate Detector + Match Engine |
| Resume parse | pypdf + python-docx | OCR fallback uses pdf2image + Tesseract |
| HTTP | httpx | LLM wrapper + GitHub checker |
| Logging | structlog | JSON output. Single config in `app/core/logging.py` |
| Config | pydantic-settings | One `Settings` object reads `.env` |

---

## 3. Prerequisites — install BEFORE you run anything

### On every OS

1. **Python 3.11** (NOT 3.12+ — pinned). Verify: `python --version` → `Python 3.11.x`
2. **Docker Desktop** (for Postgres + Redis containers).
3. **Tesseract OCR** — needed by Module 1 for image-based PDFs:
   - **Windows**: install from https://github.com/UB-Mannheim/tesseract/wiki then add `C:\Program Files\Tesseract-OCR` to PATH
   - **macOS**: `brew install tesseract`
   - **Linux**: `sudo apt install tesseract-ocr`
   - Verify: `tesseract --version`
4. **Git** (obviously) — to clone.

### Windows-specific notes

- If you already have a local **Postgres** running on `5432`, it will hijack the Docker container's port (symptom: `password authentication failed for user "hrms_ai"`). Either stop the Windows service or change `POSTGRES_PORT=5433` in `.env` and update `DATABASE_URL` accordingly.
- The Celery worker must use `--pool=solo` on Windows. The default `prefork` pool hangs.

### Disk space

- ~5 GB total: model downloads (~500 MB for sentence-transformers, plus PyTorch + transformers ~2 GB), Docker images (~500 MB), and Postgres data volume.

---

## 4. First-time setup (after cloning from GitHub)

```bash
# 1. Clone
git clone <your-repo-url> hrms_ai
cd hrms_ai

# 2. Copy the env template. Real secrets go in .env (gitignored).
cp .env.example .env          # macOS/Linux
copy .env.example .env        # Windows

# 3. (Optional) edit .env if you want to use real Grok/Groq/GitHub keys.
#    The defaults work fine for local dev with the `mock` LLM backend.

# 4. Start the database + redis (Docker must be running)
docker compose up -d

# 5. Tail DB logs the first time to verify pgvector + schema init ran cleanly
docker compose logs -f db
# Look for "database system is ready to accept connections" and our SQL init scripts running.
# Press Ctrl+C when you're satisfied — `up -d` keeps the containers running.

# 6. Create + activate a Python virtualenv
python -m venv .venv
.venv\Scripts\activate         # Windows
source .venv/bin/activate      # macOS/Linux

# 7. Install the project + all deps in editable mode
pip install -e .
# Optional dev tooling (pytest, ruff):
pip install -e ".[dev]"

# 8. Start the API
uvicorn app.main:app --reload
# Visit http://localhost:8000/docs
```

That's the full happy path. The first request to any embedding-using endpoint will download `all-mpnet-base-v2` (~420 MB). After that it's cached.

### Starting the Celery worker (separate terminal)

The Resume Parser is the only module that uses Celery today — uploads are async and you poll for status.

```bash
# Same venv, separate terminal
celery -A app.workers.celery_app worker -Q resume_parsing --pool=solo --loglevel=info
#                                                              ^^^^^^^^^^^^^
#                                               required on Windows. On Linux/macOS you can drop it
#                                               and Celery will use the default prefork pool.
```

If you don't run the worker, `POST /api/v1/resumes/parse` will return a `parse_job_id` but the job will just sit in `pending` forever.

---

## 5. Environment variables (every knob)

Full list and defaults in [.env.example](./.env.example). Highlights:

| Var | Purpose | Notes |
|---|---|---|
| `APP_ENV` | `development` / `staging` / `production` | Affects CORS permissiveness |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` | structlog level |
| `POSTGRES_PORT` | DB port mapped to host | Change to `5433` if `5432` is taken |
| `DATABASE_URL` | SQLAlchemy URL | Must use `postgresql+psycopg://` driver (not `psycopg2`) |
| `PGVECTOR_DIM` | Embedding dimensions | **Do not change** — pinned to 768 to match the model |
| `REDIS_URL` / `CELERY_BROKER_URL` | Celery broker | Both point at the same Redis. Keep them in sync |
| `LLM_BACKEND` | `mock` / `grok` / `groq` | `mock` = deterministic fake parser, no API key. Best default for first run |
| `GROK_API_KEY` / `GROQ_API_KEY` | LLM keys | Only required if you set `LLM_BACKEND` to that provider |
| `EMBEDDING_MODEL` | sentence-transformers model id | Stay on `all-mpnet-base-v2` unless you also change `PGVECTOR_DIM` |
| `GITHUB_TOKEN` | GitHub PAT | Optional; raises Module 5 rate limit from 60/hr → 5000/hr |
| `OCR_ENGINE` | `tesseract` | `paddle` is stubbed; not installed by default |
| `VECTOR_STORE_BACKEND` | `pgvector` | `pinecone` raises `DependencyError` (stub) |
| `ARTIFACTS_DIR` | Where uploaded resumes + trained models go | Gitignored. Default `./artifacts/` |
| `MODEL_VERSION` | XGBoost model version to load at startup | If no model exists for this version, Module 8 falls back to rules |

**`.env` is gitignored.** Never commit it. `.env.example` is the safe-to-commit template with placeholder/empty values.

---

## 6. API surface — every endpoint, every payload

Base URL during dev: `http://localhost:8000`. All endpoints under `/api/v1`. Swagger UI shows live examples — this section is a quick reference.

### Health

```http
GET /api/v1/health
```
Returns `{ status, db, embedding_model }`. Use to verify DB connectivity + that the embedding model loaded.

### Resume Parser (async)

```http
POST /api/v1/resumes/parse
Content-Type: multipart/form-data
file=@resume.pdf
```
Returns `202 Accepted` with `{ parse_job_id, status: "pending" }`. Celery worker handles it.

```http
GET /api/v1/resumes/parse-jobs/{parse_job_id}
```
Poll status: `pending` / `processing` / `succeeded` (with `candidate_id`) / `failed` (with `error`).

```http
GET /api/v1/resumes/{candidate_id}
```
Full parsed profile + experience + education + skills + certifications + languages.

### Embeddings

```http
POST /api/v1/embeddings/generate
{ "text": "Senior Python engineer with FastAPI", "store_as": null }
```
Returns the 768-d vector. If `store_as = { "kind": "resume", "entity_id": "..." }` is provided, also writes it to pgvector.

### Vector search

```http
POST /api/v1/vector-search/candidates
{ "query": "Senior Java backend with Spring", "top_k": 10,
  "filters": { "location": "Bengaluru", "min_experience_years": 3 } }
```
Returns top-K candidates by cosine similarity. `filters` are accepted today but **not pushed to SQL yet** — they appear in `ignored_filters` in the response. Deliberate. To be added in a small future PR.

### Match Engine

```http
POST /api/v1/match/score
{ "candidate_id": "uuid", "job_id": "uuid", "use_llm_reasoning": true }
```
Single pair. Returns composite + 6 sub-scores + LLM reasoning bullets (or rule-based fallback if LLM fails) + `cached: bool`.

```http
POST /api/v1/match/by-job
{ "job_id": "uuid", "top_k": 50 }
```
Recruiter fan-out. Returns ranked candidates with sub-scores. **No LLM per row** (would burn rate limits). Each row carries `fake_profile_risk` and within-set `possible_duplicates`.

### Candidate Ranker

```http
POST /api/v1/rank/candidates
{ "job_id": "uuid", "top_k": 25,
  "weights": { "match": 0.5, "hiring_prob": 0.25, "trust": 0.15, "seniority": 0.10 } }
```
Composes Match (45%) + Hiring Prob (30%) + Trust (15%) + Seniority (10%). Weights overridable per request, auto-normalized.

```http
POST /api/v1/rank/compare
{ "job_id": "uuid", "candidate_ids": ["uuid", "uuid", ...] }
```
Side-by-side comparison of 1–20 hand-picked candidates. Preserves input order.

### Fake Profile Detector

```http
POST /api/v1/fake-profile/score
{ "candidate_id": "uuid",
  "github_username": "optional-override",
  "force_recompute": false }
```
5 internal signals + GitHub cross-check. Returns `trust_score (0–100)`, `risk_level` (low/medium/high), `reasoning_bullets[]`, `score_breakdown[]` (every signal listed whether fired or not), `github_check{}`.

### Duplicate Job Detector

```http
POST /api/v1/jobs/duplicate-check
{ "job_id": "uuid", "top_n": 50 }
```
HNSW pre-filter → fuzzy + skills check. Verdicts: `hard` / `likely` / `similar` / `none`.

### Ghost Job Detector

```http
POST /api/v1/jobs/ghost-score
{ "job_id": "uuid", "force_recompute": false }
```
5 tiered penalties summed into `ghost_score`. Classification: `active` (<30) / `stale` (30–59) / `likely_ghost` (≥60). Returns raw signals + per-signal breakdown.

### Hiring Probability Predictor

```http
POST /api/v1/hiring-probability/predict
{ "candidate_id": "uuid", "job_id": "uuid", "force_recompute": false }
```
Returns `{ probability, confidence, model_version, model_type ("xgboost"|"rules"), features_used, shap_explanations, cached }`. Same response shape regardless of which predictor served it.

### Supporting endpoints (used by the modules above)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/jobs` | Create job + generate JD embedding |
| `GET` | `/api/v1/jobs` | List jobs (`?status=open&limit=20&offset=0`) |
| `GET` | `/api/v1/jobs/{job_id}` | Single job |
| `GET` | `/api/v1/candidates/{candidate_id}/preferences` | Read preferences (notice / salary / locations / skill_years) |
| `PUT` | `/api/v1/candidates/{candidate_id}/preferences` | Replace preferences |

---

## 7. Database schema (what lives where)

15 tables. Created automatically on first Docker boot from `db/init/02_schema.sql`.

| Table | Used by |
|---|---|
| `candidates` | parsed profile + `preferences` JSONB | 1, 3, 4 |
| `candidate_experience`, `_education`, `_skills`, `_certifications`, `_languages` | sub-records | 1, 5 |
| `parse_jobs` | async resume parse status | 1 |
| `jobs` | postings + `metadata` JSONB (required_skills, notice, salary) | 3a, 6, 7 |
| `resume_embeddings` / `job_embeddings` | `vector(768)` columns + HNSW cosine index | 2 |
| `match_scores` | composite + sub-scores + reasoning JSONB | 3 |
| `fake_profile_scores` | trust + risk + anomalies JSONB | 5 |
| `duplicate_job_clusters` | one row per pair × method | 6 |
| `ghost_job_scores` | score + classification + signals JSONB | 7 |
| `hiring_predictions` | probability + confidence + SHAP JSONB | 8 |
| `hiring_outcomes` | training labels | 8 (training) |
| `ml_models` | model registry mirror | 8 |

Indexes worth knowing:
- **HNSW cosine** on both embedding tables (`m=16, ef_construction=64`).
- **pg_trgm GIN** on `jobs.title` for Module 6's fuzzy title search.
- BTREE on FK columns + GIN on JSONB columns used in predicates.

**Schema lifecycle:** `db/init/*.sql` runs on first Docker boot only. Ongoing changes go in `scripts/migrations/NNN_*.sql` (idempotent SQL you run manually). Alembic is deferred until schema changes get complex enough to need a graph.

---

## 8. Training the XGBoost model for Module 8

Module 8 ships with a rules-based fallback so the endpoint always works. To get real predictions:

```bash
# 1. Seed some synthetic outcomes so XGBoost has labels to learn from.
#    Builds plausible hired/rejected/withdrawn/no_show rows from existing candidate × job pairs.
python -m scripts.seed_hiring_outcomes --target 200

# 2. Train. Persists to artifacts/models/v1/{model.json, metadata.json}
#    and writes a row to the `ml_models` registry table.
python -m scripts.train_model --version v1

# 3. Restart the API. It picks up the model on startup based on MODEL_VERSION env var.
```

You'll see AUC + accuracy + train/test counts in the logs. SHAP explanations use XGBoost's native `pred_contribs` (which is what the `shap` library uses internally) — no extra inference-time dependency.

---

## 9. Quick test plan — verify everything works after setup

```bash
# 1. Sanity
curl http://localhost:8000/api/v1/health

# 2. Seed dev data (postgres CLI). From the project root:
#    Run inside the docker container so you don't need a host psql install.
docker compose exec db psql -U hrms_ai -d hrms_ai -f /docker-entrypoint-initdb.d/../seed_candidates.sql
# (Or use any DB client pointed at localhost:5432, db=hrms_ai, user/pass=hrms_ai/hrms_ai.)

# 3. Open Swagger
#    → http://localhost:8000/docs
#    Every router has copy-pasteable example payloads in its docstring.

# 4. End-to-end resume parse (needs Celery worker running)
curl -X POST -F "file=@some-resume.pdf" http://localhost:8000/api/v1/resumes/parse
# → { "parse_job_id": "...", "status": "pending" }
# Poll the parse-jobs endpoint until status=succeeded, then GET /api/v1/resumes/{candidate_id}
```

The Next.js test harness under `frontendv01/` gives a click-through version of the same flow. See `frontendv01/CLAUDE.md` for how to run it (`npm install && npm run dev`, port 3000).

---

## 10. Project structure

```
hrms_ai/
├── app/
│   ├── api/v1/routers/        # one router per module (thin: validate + delegate)
│   │   ├── candidates.py      # preferences GET/PUT
│   │   ├── duplicate_jobs.py
│   │   ├── embeddings.py
│   │   ├── fake_profile.py
│   │   ├── ghost_jobs.py
│   │   ├── health.py
│   │   ├── hiring_predictor.py
│   │   ├── jobs.py            # create + list + get
│   │   ├── match.py           # single-pair + by-job fan-out
│   │   ├── ranker.py          # rank + compare
│   │   ├── resumes.py
│   │   └── vector_search.py
│   ├── core/                  # config, structlog setup, typed exceptions
│   ├── db/
│   │   ├── models/            # SQLAlchemy 2.x typed models, one per table
│   │   ├── repositories/      # the only layer that touches the DB
│   │   └── session.py
│   ├── schemas/               # Pydantic DTOs, one file per module
│   ├── services/              # business logic — one package per module
│   │   ├── duplicate_jobs/
│   │   ├── embeddings/
│   │   ├── fake_profile/      # signals.py + github.py + service.py
│   │   ├── ghost_jobs/
│   │   ├── hiring_predictor/  # features + rules + xgboost + registry + service
│   │   ├── jobs/
│   │   ├── match_engine/      # scorer (pure math) + service (orchestrator)
│   │   ├── ranker/            # composes 3+5+8
│   │   └── resume_parser/     # text_extract + ocr + service
│   ├── vector_store/          # base + pgvector + factory (Pinecone stubbed)
│   ├── llm/                   # base + openai_compatible + mock + factory + prompts
│   ├── workers/               # Celery app + tasks/resume_parser.py
│   └── main.py                # FastAPI entry, lifespan, CORS, exception handler
├── scripts/
│   ├── migrations/            # idempotent SQL migrations (manual)
│   ├── seed_candidates.sql    # dev test data
│   ├── seed_jobs.sql          # dev test data
│   ├── seed_hiring_outcomes.py
│   └── train_model.py         # XGBoost training pipeline → registry
├── db/init/                   # extensions + schema + indexes — runs ONCE on Docker first boot
├── artifacts/                 # gitignored: uploaded resumes + trained models
├── frontendv01/               # Next.js test harness (separate README/CLAUDE.md inside)
├── docker-compose.yml         # Postgres + Redis
├── .env.example               # template; copy to .env
├── pyproject.toml             # all Python deps + ruff config
└── CLAUDE.md                  # deep architecture notes (read this if you're going to extend)
```

### Architectural rules in force

- `api/` is thin — only request/response validation, delegates to `services/`.
- `services/` holds all business logic; no FastAPI imports allowed.
- `db/repositories/` is the **only** layer that touches the DB.
- `workers/` import services; services never import workers.
- `llm/` is the only place that makes HTTP calls to an LLM provider.
- All vector reads/writes go through `VectorStore`, never raw SQL.

---

## 11. Common issues & how to fix them

### `password authentication failed for user "hrms_ai"`
A local Postgres on the host is hijacking port `5432`. Fix one of:
- Stop the local Postgres service.
- Change `POSTGRES_PORT=5433` in `.env` AND update `DATABASE_URL` to `localhost:5433`. Then `docker compose down -v && docker compose up -d`.

### Celery worker doesn't pick up tasks (Windows)
You're probably using the default `prefork` pool which hangs on Windows. Always pass `--pool=solo`:
```
celery -A app.workers.celery_app worker -Q resume_parsing --pool=solo
```

### `ConnectionRefusedError [WinError 10061]` from the API on resume upload
The API didn't import the Celery app, so `kombu` fell back to AMQP defaults instead of Redis. This is wired up correctly in `app/main.py` (imports the module) and in `app/api/v1/routers/resumes.py` (uses `celery_app.send_task(...)` explicitly rather than `.delay`). If you fork or copy, keep both in place.

### Embedding model download is slow / fails
First run pulls ~420 MB from HuggingFace. If you're on a flaky network, prime the cache once:
```python
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"
```
The model lives under `~/.cache/huggingface/` after that.

### `Tesseract not found`
Tesseract is **not** a Python package — it's a native binary. Install it (see Prerequisites §3). On Windows you also need the install dir in PATH.

### `LLM_BACKEND=grok` (or `groq`) but I have no key
Either provide the key or switch back to `LLM_BACKEND=mock`. The mock backend returns deterministic fake parse results — fine for dev, useless in prod.

### `force_recompute` flag
Most module endpoints cache results in their table (`match_scores`, `ghost_job_scores`, `fake_profile_scores`, `hiring_predictions`). If you change inputs and want a fresh score, pass `"force_recompute": true`.

### `import` errors after pulling
Re-run `pip install -e .` — `pyproject.toml` may have grown new deps.

---

## 12. What is NOT in this repo (deliberately)

These are documented in `CLAUDE.md` §16 with rationale. Short list:

- **No production frontend.** `frontendv01/` is a dev tool, not a product UI.
- **No payroll, attendance, leave, performance** — out of AI scope.
- **No LinkedIn/Aadhaar/Onfido cross-check.** All require paid integrations or licenses. The `VectorStore` and `LLM` abstractions are in place so adding them later doesn't ripple.
- **No Alembic yet.** Idempotent SQL in `scripts/migrations/` is sufficient at current schema velocity.
- **No unit tests yet.** Phase 9 (hardening) work — the test harness has carried verification load up to now.
- **No Dockerfile / k8s manifests for the API and worker.** Local dev uses uvicorn + native Celery. Will be added in Phase 9.

If you're tempted to add anything in this list, talk to the owner first — `CLAUDE.md` records the reasoning behind each deferral.

---

## 13. Useful one-liners

```bash
# Spin DB + Redis up / down / wipe
docker compose up -d
docker compose down            # stops, keeps data
docker compose down -v         # stops AND wipes the DB volume (re-runs db/init/*.sql on next up)

# DB shell
docker compose exec db psql -U hrms_ai -d hrms_ai

# Tail logs
docker compose logs -f db
docker compose logs -f redis

# Run a one-off migration after editing the schema
docker compose exec -T db psql -U hrms_ai -d hrms_ai < scripts/migrations/001_add_candidate_preferences.sql

# Lint
ruff check app

# Train + seed
python -m scripts.seed_hiring_outcomes --target 200
python -m scripts.train_model --version v1
```

---

## 14. Further reading

- **`CLAUDE.md`** in this folder — full architecture, every scoring formula, every deferred item with its reason. Read this if you're going to touch the codebase, not just call it.
- **`frontendv01/CLAUDE.md`** — the test harness's own setup notes (Next.js + Tailwind v4 conventions).
- FastAPI auto-docs at **`/docs`** (Swagger) and **`/redoc`** — every endpoint has request/response schemas + example payloads from the router docstrings.

---

**Last updated:** 2026-06. Maintainer: see git log on this file.
