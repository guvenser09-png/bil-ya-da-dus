"""QuizRoyale Backend Application Configuration."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://quizroyale:quizroyale_dev_2026@localhost:5432/quizroyale"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> object:
        """Railway/Heroku gibi sağlayıcılar DATABASE_URL'yi `postgresql://` (veya
        eski `postgres://`) formatında verir; SQLAlchemy async motoru
        `postgresql+asyncpg://` ister. Ayrıca asyncpg `sslmode` query parametresini
        kabul etmez (libpq'ya özgü) → temizlenir. Böylece production'da env'den
        gelen URL'yi elle düzenlemeye gerek kalmaz."""
        if not isinstance(v, str) or not v:
            return v
        url = v
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        # asyncpg'nin anlamadığı libpq query parametrelerini ayıkla
        if "?" in url:
            base, _, query = url.partition("?")
            keep = [
                p for p in query.split("&")
                if p and not p.lower().startswith(("sslmode=", "channel_binding="))
            ]
            url = base + ("?" + "&".join(keep) if keep else "")
        return url

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRATION_MINUTES: int = 30  # 30 minutes
    JWT_REFRESH_EXPIRATION_DAYS: int = 30  # 30 days

    # Rate Limiting — limit GERÇEK istemci IP'si başınadır (X-Forwarded-For;
    # bkz. middleware/rate_limit.py + start.sh --proxy-headers). 120/dk tek bir
    # oyuncunun normal kullanımı için ferah, kötüye kullanım için hâlâ dardır.
    RATE_LIMIT_PER_MINUTE: int = 120  # general API (gerçek IP başına)
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10  # auth endpoints (login/register)

    # Anthropic AI
    ANTHROPIC_API_KEY: str = ""

    # Admin analitik ucu paylaşılan anahtarı (JWT değil). Boşsa /api/admin/metrics
    # tamamen kapalıdır (403). Production'da güçlü rastgele bir değer set edin.
    ADMIN_METRICS_KEY: str = ""

    # Push bildirimleri (Firebase Cloud Messaging HTTP v1).
    #
    # Firebase Console → Proje ayarları → Hizmet hesapları → "Yeni özel anahtar
    # oluştur" ile inilen service account JSON'unun TAMAMI (tek satır) buraya
    # konur. Railway'de Variables'a `FIREBASE_SERVICE_ACCOUNT_JSON` olarak
    # yapıştırılır (bkz. docs/FIREBASE_KURULUM.md).
    #
    # BOŞSA: push tamamen DEVRE DIŞIDIR — PushService fonksiyonları no-op olur
    # (log + sessiz dönüş). Uygulama ASLA patlamaz; token kaydı ucu yine çalışır
    # (token'lar toplanır, gönderim yapılmaz).
    #
    # Kolaylık: hem düz JSON hem base64-kodlanmış JSON kabul edilir (bazı
    # panellerde çok satırlı JSON yapıştırmak sorun çıkarır).
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""

    # Game Settings
    LOBBY_TIMEOUT_SECONDS: int = 15
    MIN_PLAYERS: int = 5
    MAX_PLAYERS: int = 12
    ROUND_COUNT: int = 5

    # Zor Mod (eski turnuva) ödül havuzu — sistem seed'i (taban havuz).
    # Az oyunculu dönemde havuz bu değerin altına düşmez: effektif_havuz =
    # max(gerçek_girişler_toplamı, ZORMOD_MIN_POOL). Prod'da env ile ayarlanır.
    # Oran (ödül %80 / sink %20) ve pay dağılımı (800/250/150) kod sabitidir
    # (tournament_service.ZORMOD_*).
    ZORMOD_MIN_POOL: int = 1000

    # AAS (Adaptive Threshold System) settings
    AAS_LEVEL_0_MAX_CAP: int = 4      # CAP 0-4: min_real=1
    AAS_LEVEL_1_MAX_CAP: int = 19     # CAP 5-19: min_real=2
    AAS_LEVEL_2_MAX_CAP: int = 49     # CAP 20-49: min_real=3
    AAS_LEVEL_3_MAX_CAP: int = 99     # CAP 50-99: min_real=4
    # CAP 100+: min_real=5 (original MIN_PLAYERS)

    AAS_LONG_WAIT_THRESHOLD: int = 40  # seconds - if player waited this long, lower threshold
    AAS_NEW_PLAYER_GAME_COUNT: int = 10  # games - below this always min_real=1
    AAS_NIGHT_START_HOUR: int = 2     # TRT night mode start
    AAS_NIGHT_END_HOUR: int = 8       # TRT night mode end

    # Reconnect window
    RECONNECT_WINDOW_SECONDS: int = 10

    # IAP (In-App Purchase) — makbuz doğrulama
    #
    # IAP_SANDBOX:
    #   True  -> DEV/STUB modu. Makbuz formatı + tutarlılık kontrol edilir ama
    #            mağazaya (Apple/Google) GERÇEK çağrı yapılmaz. SADECE geliştirme.
    #   False -> PRODUCTION. Yalnızca gerçek Apple/Google doğrulamasından geçen
    #            makbuzlar kabul edilir; sahte `sandbox_...` makbuzlar reddedilir.
    #
    # Ortam değişkeninden okunur (aşağıdaki validator). .env'de
    # `IAP_SANDBOX=false` ile production'a alın. Production'da MUTLAKA False olmalı.
    IAP_SANDBOX: bool = True
    APPLE_SHARED_SECRET: str = ""        # App Store abonelik doğrulama parolası (ZORUNLU: abonelikler)
    APPLE_BUNDLE_ID: str = ""            # örn com.bilyadadus.app — makbuz bundle_id doğrulaması (opsiyonel ama önerilir)
    GOOGLE_PACKAGE_NAME: str = ""        # örn com.bilyadadus.app
    GOOGLE_ACCESS_TOKEN: str = ""        # Play Developer API OAuth2 access token (TODO: service account ile üret)

    @field_validator("IAP_SANDBOX", mode="before")
    @classmethod
    def parse_iap_sandbox(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        # Yalnızca açıkça "doğru" benzeri değerler sandbox'ı açar; bilinmeyen/boş
        # değer GÜVENLİ tarafa (production/False) düşmez — geriye dönük uyumluluk
        # için default True'dur, ama production deploy'da açıkça False set edilmeli.
        return str(v).strip().lower() in ("true", "1", "yes", "on")

    # App Info
    APP_NAME: str = "QuizRoyale"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).lower() not in ("false", "0", "no", "release", "prod", "production")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
