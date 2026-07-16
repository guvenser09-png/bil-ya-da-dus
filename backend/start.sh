#!/usr/bin/env bash
# Production başlangıç scripti (Railway/Render/Fly vb.).
# 1) Veritabanı migration'larını uygular, 2) uvicorn'u $PORT üzerinde başlatır.
set -e

# Railway/Render $PORT ortam değişkenini enjekte eder; yoksa 8000.
PORT="${PORT:-8000}"

echo "→ Alembic migration uygulanıyor..."
uv run alembic upgrade head

echo "→ Uvicorn başlatılıyor (port $PORT)..."
# --proxy-headers + --forwarded-allow-ips: Railway edge proxy'sinin arkasındayız;
# bunlar OLMADAN request.client.host TÜM kullanıcılar için proxy'nin IP'si olur
# → rate-limit middleware'i bütün oyuncuları TEK dakikalık kovada sayar ve
# trafik arttıkça herkese rastgele 429 dağıtır ("turnuvaya girilemedi",
# reklam ödülü kaybı vb. aralıklı hatalar). X-Forwarded-For ile gerçek IP okunur.
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --no-access-log \
  --proxy-headers --forwarded-allow-ips "*"
