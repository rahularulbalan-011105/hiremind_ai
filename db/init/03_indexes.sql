-- ============================================================
-- Indexes — ANN (pgvector), FK, JSONB, and trigram.
-- ============================================================

-- ---------- pgvector ANN indexes (cosine distance) ----------
-- HNSW gives better recall/latency at the cost of larger build time and memory.
-- m / ef_construction kept at sensible defaults; tune per scale.

CREATE INDEX resume_embeddings_hnsw_cos
    ON resume_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX job_embeddings_hnsw_cos
    ON job_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------- BTREE indexes on foreign keys & hot lookup paths ----------

CREATE INDEX candidate_experience_candidate_id_idx     ON candidate_experience(candidate_id);
CREATE INDEX candidate_education_candidate_id_idx      ON candidate_education(candidate_id);
CREATE INDEX candidate_skills_candidate_id_idx         ON candidate_skills(candidate_id);
CREATE INDEX candidate_certifications_candidate_id_idx ON candidate_certifications(candidate_id);
CREATE INDEX candidate_languages_candidate_id_idx      ON candidate_languages(candidate_id);

CREATE INDEX candidates_email_idx                      ON candidates(email);
CREATE INDEX candidates_phone_idx                      ON candidates(phone);

CREATE INDEX parse_jobs_status_idx                     ON parse_jobs(status);
CREATE INDEX parse_jobs_candidate_id_idx               ON parse_jobs(candidate_id);

CREATE INDEX jobs_status_idx                           ON jobs(status);
CREATE INDEX jobs_recruiter_id_idx                     ON jobs(recruiter_id);
CREATE INDEX jobs_posted_at_idx                        ON jobs(posted_at DESC);
CREATE INDEX jobs_last_activity_at_idx                 ON jobs(last_activity_at DESC);

CREATE INDEX match_scores_job_id_idx                   ON match_scores(job_id);
CREATE INDEX match_scores_candidate_id_idx             ON match_scores(candidate_id);
CREATE INDEX match_scores_score_desc_idx               ON match_scores(score DESC);

CREATE INDEX hiring_predictions_job_id_idx             ON hiring_predictions(job_id);
CREATE INDEX hiring_predictions_candidate_id_idx       ON hiring_predictions(candidate_id);

CREATE INDEX hiring_outcomes_job_id_idx                ON hiring_outcomes(job_id);

CREATE INDEX duplicate_job_clusters_job_id_idx         ON duplicate_job_clusters(job_id);
CREATE INDEX duplicate_job_clusters_dup_idx            ON duplicate_job_clusters(duplicate_of_job_id);

-- ---------- Trigram index for fuzzy job-title matching ----------

CREATE INDEX jobs_title_trgm_idx
    ON jobs
    USING gin (title gin_trgm_ops);

-- ---------- JSONB indexes ----------

CREATE INDEX jobs_metadata_gin_idx                     ON jobs USING gin (metadata);
CREATE INDEX match_scores_reasoning_gin_idx            ON match_scores USING gin (reasoning);
CREATE INDEX hiring_predictions_shap_gin_idx           ON hiring_predictions USING gin (shap);
CREATE INDEX fake_profile_scores_anomalies_gin_idx     ON fake_profile_scores USING gin (anomalies);
CREATE INDEX ghost_job_scores_signals_gin_idx          ON ghost_job_scores USING gin (signals);
