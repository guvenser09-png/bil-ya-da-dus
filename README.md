# 🎮 QuizRoyale — Mobil Trivia Battle Royale

Fall Guys mantığında bir mobil trivia oyunu. 20 oyuncu canlı online maçta yarışır, 5 tur boyunca yanlış bilenler elenir, son turda slider tahmin sorusuna en yakın cevap veren kazanır.

## Teknoloji

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3.11+ / FastAPI |
| Veritabanı | PostgreSQL 16 |
| Cache/Realtime | Redis 7 |
| Mobil | Flutter (Dart) |
| AI | Anthropic SDK |
| Görev Kuyruğu | Celery |

## Hızlı Başlangıç

### Gereksinimler
- Docker & Docker Compose
- Python 3.11+
- uv (Python paket yöneticisi)

### Kurulum

```bash
# 1. PostgreSQL ve Redis'i başlat
docker compose up -d postgres redis

# 2. Backend bağımlılıklarını kur
cd backend
uv sync

# 3. Migration'ları çalıştır
uv run alembic upgrade head

# 4. Backend'i başlat
uv run uvicorn app.main:app --reload --port 8000
```

### API Dokümantasyonu

Backend çalışırken: [http://localhost:8000/docs](http://localhost:8000/docs)

## Proje Yapısı

```
quizroyale/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── models/    # SQLAlchemy modelleri
│   │   ├── schemas/   # Pydantic şemaları
│   │   ├── services/  # İş mantığı
│   │   ├── ws/        # WebSocket
│   │   └── utils/     # Yardımcılar
│   ├── alembic/       # DB migrations
│   └── tests/         # Testler
├── docker-compose.yml
└── README.md
```

## Geliştirme Takvimi

- **Hafta 1:** Proje kurulumu, backend iskeleti, veritabanı şeması ✅
- **Hafta 2:** Auth, kullanıcı profili, temel API
- **Hafta 3:** WebSocket, lobi sistemi, matchmaking
- **Hafta 4-12:** [CLAUDE.md'ye bak]
