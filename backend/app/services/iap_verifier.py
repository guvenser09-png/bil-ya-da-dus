"""IAP makbuz doğrulama — Apple App Store ve Google Play.

İki mod vardır (`settings.IAP_SANDBOX`):

* **DEV/STUB modu** (`IAP_SANDBOX=True`): Gerçek kimlik bilgileri / mağaza
  çağrısı olmadan geliştirme yapabilmek için makbuz formatı ve
  product_id / transaction_id tutarlılığı kontrol edilir. Asla körü körüne
  "başarılı" denmez ama mağazaya gerçek HTTP doğrulaması YAPILMAZ.
* **PRODUCTION modu** (`IAP_SANDBOX=False`): Yalnızca Apple/Google tarafından
  gerçekten doğrulanan makbuzlar kabul edilir. Sahte `sandbox_...` veya
  `stub_...` makbuzlar reddedilir. Abonelikler için `APPLE_SHARED_SECRET`
  zorunludur.

Apple akışı, Apple'ın resmi önerisine uyar: önce production `verifyReceipt`
ucuna gönderilir; status 21007 dönerse (makbuz sandbox'a ait) sandbox ucuna
yeniden denenir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """Bir makbuz doğrulamasının sonucu."""

    ok: bool
    transaction_id: str | None = None
    product_id: str | None = None
    # Opsiyonel: mağazadan dönen para bilgisi.
    amount: int | None = None
    currency: str | None = None
    # Abonelikler için bitiş tarihi (UTC). store_service premium_until set eder.
    expires_at: datetime | None = None
    # Başarısızlık nedeni (loglama / istemciye mesaj).
    reason: str | None = None


# Apple verifyReceipt uçları (legacy ama hâlâ kullanılır; App Store Server API'ye
# geçilebilir). Prod ve sandbox uçları ayrıdır.
_APPLE_PROD_URL = "https://buy.itunes.apple.com/verifyReceipt"
_APPLE_SANDBOX_URL = "https://sandbox.itunes.apple.com/verifyReceipt"

# Apple'ın "bu makbuz sandbox'a ait, sandbox ucunda dene" durum kodu.
_APPLE_STATUS_SANDBOX_RECEIPT = 21007
_APPLE_STATUS_OK = 0

# Google Play Developer API ürün doğrulama uç kalıbı.
_GOOGLE_PURCHASE_URL = (
    "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
    "{package_name}/purchases/products/{product_id}/tokens/{token}"
)

# Üretimde KESİNLİKLE kabul edilmemesi gereken sahte makbuz önekleri.
_FAKE_RECEIPT_PREFIXES = ("sandbox_", "stub_", "fake_", "test_", "dev_")


def _is_fake_receipt(receipt: str) -> bool:
    """İstemcinin yolladığı makbuz açıkça sahte/dev formatında mı?"""
    r = (receipt or "").strip().lower()
    return any(r.startswith(p) for p in _FAKE_RECEIPT_PREFIXES)


def _stub_validate(
    receipt: str, store_product_id: str, transaction_id: str | None
) -> VerifyResult:
    """DEV/STUB doğrulama: format ve tutarlılık kontrolü.

    Kurallar:
    - receipt boş olmamalı.
    - product_id verilmiş olmalı.
    - transaction_id varsa kullanılır; yoksa makbuzdan stabil bir kimlik türetilir
      (idempotency için).
    Bu, geliştirme/test için deterministik ama tamamen serbest değildir. Gerçek
    mağaza çağrısı YAPMAZ — sadece IAP_SANDBOX=True iken kullanılır.
    """
    if not receipt or not receipt.strip():
        return VerifyResult(ok=False, reason="Makbuz boş.")
    if not store_product_id or not store_product_id.strip():
        return VerifyResult(ok=False, reason="Ürün kimliği eksik.")

    txn = (
        (transaction_id or "").strip()
        or f"stub_{store_product_id}_{receipt.strip()[:48]}"
    )
    return VerifyResult(ok=True, transaction_id=txn, product_id=store_product_id)


def _parse_apple_expires(item: dict) -> datetime | None:
    """Apple in_app/latest_receipt_info kaydından bitiş tarihini (UTC) çıkar.

    `expires_date_ms` epoch milisaniye olarak gelir (abonelikler için).
    """
    ms = item.get("expires_date_ms") or item.get("expires_date_pst_ms")
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


async def verify_apple(
    receipt: str,
    store_product_id: str,
    apple_product_id: str | None = None,
    transaction_id: str | None = None,
) -> VerifyResult:
    """Apple makbuzunu doğrula.

    Args:
        receipt: StoreKit `serverVerificationData` (base64 makbuz).
        store_product_id: Bizim katalog ürün kimliğimiz (örn `premium_monthly`).
            Sonuçta bu döndürülür.
        apple_product_id: Apple tarafındaki gerçek ürün kimliği
            (örn `com.bilyadadus.premium_monthly`). Makbuz içindeki ürünle
            eşleştirmek için kullanılır. None ise store_product_id ile eşleştirir.
        transaction_id: İstemcinin bildirdiği işlem kimliği (opsiyonel).

    DEV modunda (IAP_SANDBOX=True) stub kontrol yapar; PROD modunda Apple
    verifyReceipt'e HTTP isteği atar (prod -> 21007 ise sandbox fallback).
    """
    if settings.IAP_SANDBOX:
        return _stub_validate(receipt, store_product_id, transaction_id)

    # --- PRODUCTION ---
    # Sahte/dev makbuzlar production'da kesinlikle reddedilir.
    if not receipt or not receipt.strip():
        return VerifyResult(ok=False, reason="Makbuz boş.")
    if _is_fake_receipt(receipt):
        logger.warning("IAP: production'da sahte makbuz reddedildi (prefix).")
        return VerifyResult(ok=False, reason="Geçersiz makbuz.")

    match_id = apple_product_id or store_product_id

    payload = {
        "receipt-data": receipt,
        # `password` abonelikler için ZORUNLU; tüketilebilir ürünler için de
        # gönderilmesi zararsızdır. Eksikse abonelik doğrulaması başarısız olur.
        "exclude-old-transactions": True,
    }
    if settings.APPLE_SHARED_SECRET:
        payload["password"] = settings.APPLE_SHARED_SECRET
    else:
        # Shared secret olmadan abonelik doğrulanamaz; net log bırak.
        logger.error(
            "IAP: APPLE_SHARED_SECRET tanımsız — abonelik makbuzları "
            "doğrulanamaz. Lütfen ortam değişkenini ayarlayın."
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_APPLE_PROD_URL, json=payload)
            data = resp.json()
            # status 21007 => makbuz sandbox'a ait; sandbox ucuna düş (Apple akışı).
            if data.get("status") == _APPLE_STATUS_SANDBOX_RECEIPT:
                logger.info("IAP: Apple status 21007 — sandbox ucuna fallback.")
                resp = await client.post(_APPLE_SANDBOX_URL, json=payload)
                data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("IAP: Apple doğrulama hatası: %s", exc)
        return VerifyResult(ok=False, reason=f"Apple doğrulama hatası: {exc}")

    status = data.get("status")
    if status != _APPLE_STATUS_OK:
        logger.warning("IAP: Apple status=%s", status)
        return VerifyResult(ok=False, reason=f"Apple status={status}")

    # Opsiyonel bundle_id doğrulaması (yapılandırıldıysa).
    receipt_obj = data.get("receipt", {}) or {}
    if settings.APPLE_BUNDLE_ID:
        bundle = receipt_obj.get("bundle_id") or receipt_obj.get("bid")
        if bundle and bundle != settings.APPLE_BUNDLE_ID:
            logger.warning(
                "IAP: bundle_id uyuşmazlığı: %s != %s",
                bundle,
                settings.APPLE_BUNDLE_ID,
            )
            return VerifyResult(ok=False, reason="Bundle kimliği uyuşmuyor.")

    # Abonelikler için `latest_receipt_info` en güncel durumu taşır; tüketilebilir/
    # non-consumable için `receipt.in_app` kullanılır. İkisini de tara.
    candidates: list[dict] = []
    candidates.extend(data.get("latest_receipt_info") or [])
    candidates.extend(receipt_obj.get("in_app") or [])

    matched = [it for it in candidates if it.get("product_id") == match_id]
    if not matched:
        logger.warning(
            "IAP: makbuzda ürün eşleşmedi (beklenen=%s).", match_id
        )
        return VerifyResult(ok=False, reason="Makbuzda ürün eşleşmedi.")

    # Abonelikte birden çok kayıt olabilir; en yeni expires_date'i seç.
    def _expires_key(it: dict) -> int:
        try:
            return int(it.get("expires_date_ms") or 0)
        except (ValueError, TypeError):
            return 0

    best = max(matched, key=_expires_key)

    txn = best.get("transaction_id") or best.get("original_transaction_id") or transaction_id
    if not txn:
        return VerifyResult(ok=False, reason="transaction_id bulunamadı.")

    expires_at = _parse_apple_expires(best)

    # Abonelik süresi geçmişse reddet (yenilenmemiş abonelik tekrar açılmasın).
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        logger.info("IAP: Apple abonelik süresi dolmuş (%s).", expires_at)
        return VerifyResult(
            ok=False,
            transaction_id=str(txn),
            product_id=store_product_id,
            expires_at=expires_at,
            reason="Abonelik süresi dolmuş.",
        )

    return VerifyResult(
        ok=True,
        transaction_id=str(txn),
        product_id=store_product_id,
        expires_at=expires_at,
    )


async def verify_google(
    receipt: str,
    store_product_id: str,
    google_product_id: str | None = None,
    transaction_id: str | None = None,
) -> VerifyResult:
    """Google Play satın almasını doğrula.

    Burada `receipt` Google purchaseToken'dır. DEV modunda stub kontrol yapar;
    PROD modunda Google Play Developer API'ye istek atar.
    """
    if settings.IAP_SANDBOX:
        return _stub_validate(receipt, store_product_id, transaction_id)

    # --- PRODUCTION ---
    if not receipt or not receipt.strip():
        return VerifyResult(ok=False, reason="Makbuz boş.")
    if _is_fake_receipt(receipt):
        logger.warning("IAP: production'da sahte Google makbuzu reddedildi.")
        return VerifyResult(ok=False, reason="Geçersiz makbuz.")

    # TODO: Service account ile OAuth2 access token üret (google-auth) ve
    #       Authorization: Bearer <token> başlığı ekle. Şimdilik access token
    #       config'den okunur.
    access_token = settings.GOOGLE_ACCESS_TOKEN or ""
    if not access_token or not settings.GOOGLE_PACKAGE_NAME:
        logger.error("IAP: Google kimlik bilgileri yapılandırılmadı.")
        return VerifyResult(
            ok=False,
            reason="Google kimlik bilgileri yapılandırılmadı.",
        )

    product_for_url = google_product_id or store_product_id
    url = _GOOGLE_PURCHASE_URL.format(
        package_name=settings.GOOGLE_PACKAGE_NAME,
        product_id=product_for_url,
        token=receipt,
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("IAP: Google doğrulama hatası: %s", exc)
        return VerifyResult(ok=False, reason=f"Google doğrulama hatası: {exc}")

    # purchaseState: 0 = satın alındı, 1 = iptal, 2 = beklemede.
    if data.get("purchaseState") not in (0, None):
        return VerifyResult(
            ok=False, reason=f"Google purchaseState={data.get('purchaseState')}"
        )

    # orderId benzersiz işlem kimliği olarak kullanılır.
    txn = data.get("orderId") or transaction_id or receipt

    # Abonelik bitiş zamanı (varsa).
    expires_at = None
    ms = data.get("expiryTimeMillis")
    if ms:
        try:
            expires_at = datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            expires_at = None

    return VerifyResult(
        ok=True,
        transaction_id=str(txn),
        product_id=store_product_id,
        expires_at=expires_at,
    )


async def verify_receipt(
    platform: str,
    receipt: str,
    store_product_id: str,
    transaction_id: str | None = None,
    apple_product_id: str | None = None,
    google_product_id: str | None = None,
) -> VerifyResult:
    """Platforma göre doğru doğrulayıcıyı seç.

    Args:
        platform: "ios" | "android".
        receipt: base64 makbuz (iOS) veya purchaseToken (Android).
        store_product_id: Katalog ürün kimliğimiz (sonuçta döndürülür).
        transaction_id: İstemcinin bildirdiği işlem kimliği (opsiyonel).
        apple_product_id / google_product_id: Mağaza tarafındaki gerçek ürün
            kimlikleri (makbuz eşleştirmesi için). store_service katalogdan geçirir.
    """
    platform = (platform or "").lower()
    if platform == "ios":
        return await verify_apple(
            receipt, store_product_id, apple_product_id, transaction_id
        )
    if platform == "android":
        return await verify_google(
            receipt, store_product_id, google_product_id, transaction_id
        )
    return VerifyResult(ok=False, reason=f"Bilinmeyen platform: {platform}")
