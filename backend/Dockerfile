FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Copy application code
COPY . .

# Başlangıç scriptini çalıştırılabilir yap
RUN chmod +x start.sh

# Expose (yerel/dev için; production'da $PORT kullanılır)
EXPOSE 8000

# Production: migration uygula + uvicorn'u $PORT üzerinde başlat
CMD ["./start.sh"]
