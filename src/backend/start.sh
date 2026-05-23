#!/bin/sh
set -e

echo "[start.sh] Running alembic migrations..."
alembic upgrade head

echo "[start.sh] Ensuring configured admin account..."
python -m app.seeders.seed_admin

echo "[start.sh] Seeding runtime data from ${PROCESSED_DATA_DIR:-/app/data/processed}..."
python -m app.seeders.seed_processed --only vocabulary,error_bank,pedagogical_prompt,ielts_writing_sample || echo "[start.sh] WARN: seed_processed exited non-zero; continuing"

PORT="${PORT:-8000}"
echo "[start.sh] Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips="*"
