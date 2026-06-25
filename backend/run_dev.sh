#!/usr/bin/env bash
# Bil ya da Düş — yerel backend'i başlatır (Postgres + Redis brew ile çalışıyor olmalı).
set -e
cd "$(dirname "$0")"

export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
export SSL_CERT_FILE=${SSL_CERT_FILE:-/opt/homebrew/etc/ca-certificates/cert.pem}

# Postgres/Redis çalışıyor mu (brew services)
brew services list 2>/dev/null | grep -qE "postgresql@16\s+started" || echo "UYARI: postgresql@16 çalışmıyor → 'brew services start postgresql@16'"
brew services list 2>/dev/null | grep -qE "redis\s+started" || echo "UYARI: redis çalışmıyor → 'brew services start redis'"

# Rol + veritabanı (yoksa oluştur)
psql -d postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='quizroyale'" | grep -q 1 \
  || psql -d postgres -c "CREATE ROLE quizroyale LOGIN PASSWORD 'quizroyale_dev_2026';"
psql -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='quizroyale'" | grep -q 1 \
  || psql -d postgres -c "CREATE DATABASE quizroyale OWNER quizroyale;"

# Bağımlılıklar + migration
uv sync
uv run alembic upgrade head

# Sunucu
echo "→ http://localhost:8000 (iOS simülatörü de localhost ile erişir)"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
