"""Push bildirimi servisi — FCM HTTP v1 (kimlik bilgisi yoksa no-op).

TASARIM İLKESİ: Bu servis ASLA patlamaz. Firebase service account JSON'u
yapılandırılmamışsa (settings.FIREBASE_SERVICE_ACCOUNT_JSON boş) tüm gönderim
fonksiyonları sessizce no-op döner (log + boş istatistik). Token kaydı ucu yine
çalışır → Firebase kurulunca birikmiş token'lara hemen gönderim yapılabilir.

Neden google-auth DEĞİL? Yeni bağımlılık eklemeden, mevcut `python-jose
[cryptography]` (RS256 imza) + `httpx` ile OAuth2 "JWT bearer" akışı elle
yapılır:
    1. Service account private key ile RS256 imzalı bir JWT assertion üret.
    2. https://oauth2.googleapis.com/token adresinden erişim jetonu al (~1 saat).
    3. FCM v1 uç noktasına Bearer ile gönder.
Erişim jetonu süresi dolana kadar bellekte önbelleklenir.

KULLANICI KORUMASI (spam yok):
  • Sessiz saat: 23:00–10:00 TRT arası gönderim YAPILMAZ.
  • Kişi başı GÜNDE EN FAZLA 1 push (Redis'te TRT-gün bazlı kilit).
  • Geçersiz (UNREGISTERED/INVALID_ARGUMENT) token'lar DB'den otomatik silinir.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import httpx
from jose import jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import redis_client
from app.config import settings
from app.models.device_token import DeviceToken

logger = logging.getLogger("app.push")

TRT = ZoneInfo("Europe/Istanbul")

# Sessiz saat penceresi (TRT). [23:00, 10:00) arasında gönderim yapılmaz.
QUIET_START_HOUR = 23
QUIET_END_HOUR = 10

# Kişi başı günlük push limiti (TRT günü). Kilit anahtarı 48 saat yaşar.
_DAILY_CAP_TTL_SECONDS = 48 * 3600

# OAuth2 / FCM uç noktaları
_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

# Aynı anda açık FCM isteği sayısı (kibar davran, rate limit yeme).
_MAX_CONCURRENCY = 10
_HTTP_TIMEOUT = 10.0

# Erişim jetonu önbelleği: (token, expires_at_epoch)
_access_token_cache: tuple[str, float] | None = None

# Geçersiz token'ı işaret eden FCM hata kodları.
_INVALID_TOKEN_ERRORS = {
    "UNREGISTERED",           # token artık geçerli değil (uygulama silinmiş)
    "INVALID_ARGUMENT",       # token biçimi bozuk
    "SENDER_ID_MISMATCH",     # token başka bir Firebase projesine ait
}


# ---------------------------------------------------------------------------
# Kimlik bilgisi (service account)
# ---------------------------------------------------------------------------

def _load_service_account() -> dict[str, Any] | None:
    """settings.FIREBASE_SERVICE_ACCOUNT_JSON'u çözer; yoksa/bozuksa None.

    Hem düz JSON hem base64-kodlanmış JSON kabul edilir (bazı panellerde çok
    satırlı JSON yapıştırmak sorun çıkarır). Bozuk değer ASLA istisna fırlatmaz
    → yalnızca log + None (push devre dışı).
    """
    raw = (settings.FIREBASE_SERVICE_ACCOUNT_JSON or "").strip()
    if not raw:
        return None

    if not raw.startswith("{"):
        # base64 olabilir
        try:
            raw = base64.b64decode(raw).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            logger.error("FIREBASE_SERVICE_ACCOUNT_JSON base64 çözülemedi: %s", exc)
            return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("FIREBASE_SERVICE_ACCOUNT_JSON geçerli JSON değil: %s", exc)
        return None

    required = ("project_id", "private_key", "client_email")
    missing = [k for k in required if not data.get(k)]
    if missing:
        logger.error(
            "FIREBASE_SERVICE_ACCOUNT_JSON eksik alan(lar): %s → push devre dışı",
            ", ".join(missing),
        )
        return None
    return data


def is_configured() -> bool:
    """Push gönderimi yapılandırılmış mı? (service account var ve geçerli mi)"""
    return _load_service_account() is not None


def reset_credentials_cache() -> None:
    """Erişim jetonu önbelleğini temizler (testler ve anahtar değişimi için)."""
    global _access_token_cache
    _access_token_cache = None


async def _get_access_token() -> str | None:
    """Google OAuth2 erişim jetonu (önbellekli). Kimlik yoksa/hata varsa None."""
    global _access_token_cache

    now = time.time()
    if _access_token_cache and _access_token_cache[1] > now + 60:
        return _access_token_cache[0]

    sa = _load_service_account()
    if not sa:
        return None

    token_uri = sa.get("token_uri") or _OAUTH_TOKEN_URL
    issued_at = int(now)
    assertion_claims = {
        "iss": sa["client_email"],
        "scope": _FCM_SCOPE,
        "aud": token_uri,
        "iat": issued_at,
        "exp": issued_at + 3600,
    }

    try:
        assertion = jwt.encode(
            assertion_claims,
            sa["private_key"],
            algorithm="RS256",
            headers={"kid": sa.get("private_key_id", "")},
        )
    except Exception as exc:  # bozuk private key → push'u kapat, patlama
        logger.error("Firebase JWT imzalanamadı (private_key bozuk?): %s", exc)
        return None

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as http:
            resp = await http.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
        if resp.status_code != 200:
            logger.error(
                "Google erişim jetonu alınamadı (%s): %s", resp.status_code, resp.text[:300]
            )
            return None
        payload = resp.json()
    except Exception as exc:
        logger.error("Google erişim jetonu isteği başarısız: %s", exc)
        return None

    access_token = payload.get("access_token")
    if not access_token:
        logger.error("Google yanıtında access_token yok.")
        return None

    expires_in = int(payload.get("expires_in", 3600))
    _access_token_cache = (access_token, now + expires_in)
    return access_token


# ---------------------------------------------------------------------------
# Sessiz saat + günlük limit
# ---------------------------------------------------------------------------

def trt_now(now: datetime | None = None) -> datetime:
    """Şu anın TRT karşılığı."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(TRT)


def trt_day(now: datetime | None = None) -> str:
    """TRT gün damgası (YYYY-MM-DD) — günlük limit anahtarında kullanılır."""
    return trt_now(now).strftime("%Y-%m-%d")


def is_quiet_hours(now: datetime | None = None) -> bool:
    """Şu an sessiz saatte miyiz? (23:00–10:00 TRT arası → True)"""
    hour = trt_now(now).hour
    # Pencere gece yarısını aştığı için OR ile kontrol edilir.
    return hour >= QUIET_START_HOUR or hour < QUIET_END_HOUR


def _daily_cap_key(user_id: str, now: datetime | None = None) -> str:
    return f"push:sent:{user_id}:{trt_day(now)}"


async def try_consume_daily_quota(user_id: str, now: datetime | None = None) -> bool:
    """Kullanıcının bugünkü tek push hakkını REZERVE etmeye çalışır.

    Redis'te SET NX ile atomik kilit alır: bugün zaten push aldıysa False döner.
    Redis erişilemezse GÜVENLİ tarafa düşer (False → gönderme). Böylece "günde
    en fazla 1 push" kuralı Redis çöktüğünde de ihlal edilmez.
    """
    try:
        redis = await redis_client.get_redis()
        ok = await redis.set(
            _daily_cap_key(user_id, now), "1", ex=_DAILY_CAP_TTL_SECONDS, nx=True
        )
        return bool(ok)
    except Exception as exc:
        logger.warning(
            "Günlük push kotası kontrol edilemedi (Redis) → gönderim atlandı: %s", exc
        )
        return False


async def release_daily_quota(user_id: str, now: datetime | None = None) -> None:
    """Rezerve edilen günlük hakkı geri verir (gönderim başarısız olursa)."""
    try:
        redis = await redis_client.get_redis()
        await redis.delete(_daily_cap_key(user_id, now))
    except Exception as exc:
        logger.debug("Günlük push kotası geri verilemedi: %s", exc)


# ---------------------------------------------------------------------------
# Token deposu (DB)
# ---------------------------------------------------------------------------

async def register_token(
    db: AsyncSession,
    user_id: str,
    token: str,
    platform: str = "ios",
) -> DeviceToken:
    """Cihaz token'ını kaydeder/günceller (upsert).

    Token küresel TEKİL olduğu için: aynı token başka bir kullanıcıya bağlıysa
    (cihaz el değiştirdi / hesap değişti) kayıt YENİ kullanıcıya taşınır.
    """
    platform = (platform or "ios").lower()
    if platform not in ("ios", "android"):
        platform = "ios"

    existing = await db.scalar(select(DeviceToken).where(DeviceToken.token == token))
    if existing:
        existing.user_id = uuid.UUID(str(user_id))
        existing.platform = platform
        # updated_at onupdate ile tazelenir; SQLite'ta onupdate tetiklensin diye
        # alanı açıkça dokunmuyoruz — SQLAlchemy değişiklik görürse yazar.
        existing.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return existing

    row = DeviceToken(
        id=uuid.uuid4(),
        user_id=uuid.UUID(str(user_id)),
        token=token,
        platform=platform,
    )
    db.add(row)
    await db.flush()
    return row


async def remove_token(db: AsyncSession, token: str) -> int:
    """Tek bir cihaz token'ını siler (çıkış / bildirim kapatma). Silinen satır sayısı."""
    result = await db.execute(delete(DeviceToken).where(DeviceToken.token == token))
    await db.flush()
    return int(result.rowcount or 0)


async def remove_user_tokens(db: AsyncSession, user_id: str) -> int:
    """Kullanıcının TÜM cihaz token'larını siler (hesap silme akışı)."""
    result = await db.execute(
        delete(DeviceToken).where(DeviceToken.user_id == uuid.UUID(str(user_id)))
    )
    await db.flush()
    return int(result.rowcount or 0)


async def get_tokens_for_users(
    db: AsyncSession, user_ids: Iterable[str]
) -> dict[str, list[str]]:
    """Kullanıcı → token listesi eşlemesi (token'ı olmayan kullanıcı sözlükte yok)."""
    ids = [uuid.UUID(str(u)) for u in user_ids]
    if not ids:
        return {}
    rows = await db.execute(
        select(DeviceToken.user_id, DeviceToken.token).where(DeviceToken.user_id.in_(ids))
    )
    out: dict[str, list[str]] = {}
    for user_id, token in rows.all():
        out.setdefault(str(user_id), []).append(token)
    return out


# ---------------------------------------------------------------------------
# Gönderim
# ---------------------------------------------------------------------------

def _build_message(
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None,
) -> dict[str, Any]:
    """FCM v1 mesaj gövdesi. `data` değerleri STRING olmak ZORUNDA (FCM kuralı)."""
    payload: dict[str, Any] = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "apns": {
                "headers": {"apns-priority": "10"},
                "payload": {"aps": {"sound": "default", "badge": 1}},
            },
            "android": {
                "priority": "high",
                "notification": {"sound": "default"},
            },
        }
    }
    if data:
        payload["message"]["data"] = {str(k): str(v) for k, v in data.items()}
    return payload


async def _send_one(
    http: httpx.AsyncClient,
    url: str,
    access_token: str,
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None,
) -> tuple[str, str]:
    """Tek token'a gönder. (durum, token) döner.

    durum: "sent" | "invalid" (token silinmeli) | "error"
    """
    try:
        resp = await http.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=_build_message(token, title, body, data),
        )
    except Exception as exc:
        logger.warning("FCM isteği başarısız: %s", exc)
        return ("error", token)

    if resp.status_code == 200:
        return ("sent", token)

    # Hata kodunu ayıkla (FCM v1: error.details[].errorCode veya error.status)
    code = ""
    try:
        err = resp.json().get("error", {})
        code = str(err.get("status") or "")
        for detail in err.get("details", []) or []:
            if detail.get("errorCode"):
                code = str(detail["errorCode"])
                break
    except Exception:
        pass

    if resp.status_code in (400, 403, 404) and code in _INVALID_TOKEN_ERRORS:
        logger.info("Geçersiz FCM token (%s) → silinecek", code)
        return ("invalid", token)

    logger.warning("FCM gönderimi başarısız (%s): %s", resp.status_code, resp.text[:200])
    return ("error", token)


async def send_to_tokens(
    db: AsyncSession,
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> dict[str, int]:
    """Verilen token listesine toplu gönderim. Geçersiz token'ları DB'den siler.

    Kimlik bilgisi YOKSA: no-op → {"sent": 0, "invalid": 0, "error": 0,
    "skipped": len(tokens), "disabled": 1}. ASLA istisna fırlatmaz.
    """
    stats = {"sent": 0, "invalid": 0, "error": 0, "skipped": 0, "disabled": 0}
    if not tokens:
        return stats

    sa = _load_service_account()
    if not sa:
        logger.info(
            "Push devre dışı (FIREBASE_SERVICE_ACCOUNT_JSON yok) → %d token atlandı.",
            len(tokens),
        )
        stats["skipped"] = len(tokens)
        stats["disabled"] = 1
        return stats

    access_token = await _get_access_token()
    if not access_token:
        stats["skipped"] = len(tokens)
        stats["disabled"] = 1
        return stats

    url = _FCM_ENDPOINT.format(project_id=sa["project_id"])
    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    invalid: list[str] = []

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as http:
        async def _guarded(tok: str) -> tuple[str, str]:
            async with semaphore:
                return await _send_one(http, url, access_token, tok, title, body, data)

        results = await asyncio.gather(
            *(_guarded(t) for t in tokens), return_exceptions=True
        )

    for res in results:
        if isinstance(res, BaseException):
            stats["error"] += 1
            continue
        status, tok = res
        stats[status] = stats.get(status, 0) + 1
        if status == "invalid":
            invalid.append(tok)

    # Geçersiz token'ları temizle (bir sonraki kampanyayı kirletmesin).
    if invalid:
        try:
            await db.execute(delete(DeviceToken).where(DeviceToken.token.in_(invalid)))
            await db.commit()
            logger.info("%d geçersiz cihaz token'ı silindi.", len(invalid))
        except Exception as exc:
            await db.rollback()
            logger.warning("Geçersiz token'lar silinemedi: %s", exc)

    return stats


async def send_to_users(
    db: AsyncSession,
    user_ids: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    *,
    respect_quiet_hours: bool = True,
    respect_daily_cap: bool = True,
    now: datetime | None = None,
) -> dict[str, int]:
    """Kullanıcı listesine push gönderir (sessiz saat + günlük limit uygulanır).

    Dönen istatistik: sent / invalid / error / skipped / disabled /
    quiet_hours (1 ise sessiz saatte hiç gönderilmedi) / capped (günlük limiti
    dolduğu için atlanan kullanıcı sayısı) / no_token (token'ı olmayan kullanıcı).

    Kimlik bilgisi yoksa gönderim yapılmaz ama günlük kota da TÜKETİLMEZ
    (kullanıcı boşuna "bugün push aldı" sayılmasın).
    """
    stats = {
        "sent": 0, "invalid": 0, "error": 0, "skipped": 0, "disabled": 0,
        "quiet_hours": 0, "capped": 0, "no_token": 0, "users": 0,
    }
    if not user_ids:
        return stats

    if respect_quiet_hours and is_quiet_hours(now):
        logger.info("Sessiz saat (23:00–10:00 TRT) → push gönderilmedi.")
        stats["quiet_hours"] = 1
        stats["skipped"] = len(user_ids)
        return stats

    if not is_configured():
        logger.info("Push devre dışı (kimlik bilgisi yok) → %d kullanıcı atlandı.", len(user_ids))
        stats["disabled"] = 1
        stats["skipped"] = len(user_ids)
        return stats

    token_map = await get_tokens_for_users(db, user_ids)

    to_send: list[str] = []
    for uid in user_ids:
        tokens = token_map.get(str(uid))
        if not tokens:
            stats["no_token"] += 1
            continue
        if respect_daily_cap and not await try_consume_daily_quota(str(uid), now):
            stats["capped"] += 1
            continue
        stats["users"] += 1
        to_send.extend(tokens)

    if not to_send:
        return stats

    send_stats = await send_to_tokens(db, to_send, title, body, data)
    for key in ("sent", "invalid", "error", "skipped", "disabled"):
        stats[key] += send_stats.get(key, 0)
    return stats
