# db/

The AI service **no longer owns** any Postgres schemas. The live tables it reads
and writes live in three databases owned by their respective microservices:

| Database              | Owner service     | What the AI uses                                              |
| --------------------- | ----------------- | ------------------------------------------------------------- |
| `hiremind_candidate`  | candidate-service | Reads `candidate*`, writes `parse_jobs`, `resume_embeddings`, `fake_profile_scores` |
| `hiremind_company`    | company-service   | Reads `jobs*`, writes `job_embeddings`, `match_scores`, `ghost_job_scores`, `duplicate_job_clusters`, `hiring_predictions`, `hiring_outcomes`, `ml_models` |
| `hiremind_users`      | users-service     | Read-only, optional                                           |

All schema changes happen through the Flyway migrations in each Spring Boot
service's own repo (`V1__…`, `V2__…`, etc.). The AI columns we depend on were
added in:

* `candidate-service` — `V9__ai_candidate_tables.sql`, `V10__add_ai_candidate_columns.sql`, `V11__add_ai_candidate_spec_columns.sql`
* `company-service`   — `V10__ai_company_tables.sql`, `V11__add_ai_company_columns.sql`, `V12__add_ai_company_spec_columns.sql`

## `init.legacy/`

These are the standalone init scripts from when the AI service ran its own
Postgres. They're kept around purely for reference — DO NOT run them against
the live databases, they will conflict with the Spring services' Flyway state.
