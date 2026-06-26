#!/usr/bin/env bash
# Creates the three databases the AI service expects, against the local
# Postgres started by `docker compose up -d db`. Idempotent — re-runnable.
#
# The Spring Boot services normally create their own databases via Flyway,
# but if you only want the AI service running locally you can use this
# script to bootstrap empty DBs and rely on the schemas being created by
# the Flyway migrations from each service.
set -euo pipefail

PSQL="docker exec -i hiremind_db psql -U ${POSTGRES_USER:-postgres}"

for db in hiremind_candidate hiremind_company hiremind_users; do
  $PSQL -tc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 \
    || $PSQL -c "CREATE DATABASE \"$db\";"
  echo "[ok] $db"
done

# Required extensions — enabled per-DB
for db in hiremind_candidate hiremind_company; do
  $PSQL -d "$db" -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null
  $PSQL -d "$db" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" >/dev/null
  $PSQL -d "$db" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" >/dev/null
done

echo
echo "All three databases are ready. Now run the candidate-service + company-service"
echo "Spring Boot apps so Flyway populates the schemas — the AI service is a consumer."
