#!/usr/bin/env bash
# Production başlangıç scripti (Railway/Render/Fly vb.).
# 1) Veritabanı migration'larını uygular, 2) uvicorn'u $PORT üzerinde başlatır.
set -e

# Railway/Render $PORT ortam değişkenini enjekte eder; yoksa 8000.
PORT="${PORT:-8000}"

echo "→ Alembic migration uygulanıyor..."
uv run alembic upgrade head

echo "→ Uvicorn başlatılıyor (port $PORT)..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --no-access-log
