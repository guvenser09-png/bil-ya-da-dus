# 🚀 Bil ya da Düş — Production Deploy Rehberi (Railway)

Backend (FastAPI + Postgres + Redis + WebSocket) Railway'e deploy edilir. Kod tarafı
hazır; aşağıdaki adımları **senin Railway hesabınla** uygulaman gerekir (hesap + fatura).

---

## 0. Ön hazırlık (yapıldı ✅)
- `Dockerfile` → production `start.sh` ile çalışıyor (migration + uvicorn `$PORT`).
- `start.sh` → `alembic upgrade head` + uvicorn `$PORT`.
- `app/config.py` → `DATABASE_URL`'yi otomatik `postgresql+asyncpg://`'ye çeviriyor, `sslmode`'u ayıklıyor.
- `railway.json` → Dockerfile build + `/health` healthcheck.

---

## 1. Railway projesi oluştur
1. https://railway.app → **GitHub ile giriş** yap.
2. **New Project → Deploy from GitHub repo** → bu repoyu seç.
3. Servis ayarlarında **Root Directory = `backend`** yap (repo kökü değil!).
   - Railway `backend/Dockerfile` ve `backend/railway.json`'ı otomatik bulur.

## 2. Postgres + Redis ekle
1. Proje içinde **New → Database → Add PostgreSQL**.
2. Tekrar **New → Database → Add Redis**.
3. Railway bunlar için `DATABASE_URL` ve `REDIS_URL` değişkenlerini otomatik üretir.
   - Backend servisinde **Variables → Reference** ile Postgres'in `DATABASE_URL`'ini
     ve Redis'in `REDIS_URL`'ini backend servisine bağla (Add Reference Variable).

## 3. Ortam değişkenleri (backend servisi → Variables)
Aşağıdakileri ekle:

| Değişken | Değer |
|---|---|
| `DATABASE_URL` | (Postgres referansı — Railway otomatik) |
| `REDIS_URL` | (Redis referansı — Railway otomatik) |
| `SECRET_KEY` | **güçlü rastgele** bir değer (örn. `openssl rand -hex 32`) |
| `DEBUG` | `false` |
| `IAP_SANDBOX` | `false`  ← **production'da MUTLAKA false** |
| `APPLE_SHARED_SECRET` | App Store Connect → App-Specific Shared Secret |
| `APPLE_BUNDLE_ID` | Seçtiğin tek bundle id (örn. `com.quizroyale.quizroyale`) |
| `ANTHROPIC_API_KEY` | (AI soru üretimi kullanılacaksa) |

## 4. Deploy
- Railway, push'ta otomatik build + deploy eder. `start.sh` migration'ları uygular.
- **Settings → Networking → Generate Domain** ile public HTTPS domaini al
  (örn. `https://bilyadadus-production.up.railway.app`).

## 5. Soru bankasını seed'le (tek seferlik)
Deploy sonrası soruları production DB'ye yükle. Railway servis **Shell**'inde
(veya lokal `railway run` ile):
```bash
uv run python scripts/seed_questions.py
```
(Görsel sorular için ayrıca: `uv run python scripts/insert_gorsel.py` — gerekiyorsa.)

## 6. Doğrula
```bash
curl https://<railway-domain>/health
# {"status":"healthy", ...}
```

## 7. Mobil uygulamayı production'a yönelt
Flutter derlemesinde domaini `--dart-define` ile geç:
```bash
flutter build ipa \
  --dart-define=API_BASE_URL=https://<railway-domain> \
  --dart-define=WS_BASE_URL=wss://<railway-domain>
```
(WebSocket için `wss://` — Railway HTTPS domaini WS'i de TLS ile taşır.)

---

## Notlar
- **CORS** şu an `*` (mobil app için uygun). İstersen production'da kendi domainlerinle kısıtla.
- **Ölçek:** Railway tek instance'ta WebSocket + in-memory oyun state'i sorunsuz çalışır.
  Çok instance'a çıkarsan oyun state'inin Redis'e taşınması gerekir (şu an tek instance varsayımı).
- **Maliyet:** Railway ~$5/ay kredi ile başlar; Postgres + Redis + backend küçük ölçekte bu banda sığar.
- **Alternatif:** Fly.io (daha iyi WS bölge latensi) veya Render. Aynı Dockerfile çalışır.
