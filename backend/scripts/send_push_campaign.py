"""Retention push kampanyası gönderici (CLI).

Kampanyalar (hedef seçimi: app/services/push_campaign_service.py):

  streak    Günlük ödül serisi BUGÜN bozulacak olanlar.   → 20:00 TRT'de çalıştır
  daily     Bugün "Günün Sorusu"nu oynamamış aktifler.    → 12:00 TRT'de çalıştır
  comeback  3+ gündür dönmeyenler (son 30 günde görülmüş). → esnek (gündüz)

GÜVENLİK KORKULUKLARI (otomatik, kod tarafında):
  • Sessiz saat 23:00–10:00 TRT → gönderim YAPILMAZ (script hemen çıkar).
  • Kişi başı GÜNDE EN FAZLA 1 push (Redis kilidi; kampanyalar arası da geçerli).
  • FIREBASE_SERVICE_ACCOUNT_JSON yoksa: hedefler yine listelenir, gönderim
    yapılmaz (no-op) — script ASLA patlamaz.

Kullanım (backend dizininden)::

    .venv/bin/python scripts/send_push_campaign.py --campaign daily --dry-run
    .venv/bin/python scripts/send_push_campaign.py --campaign streak
    .venv/bin/python scripts/send_push_campaign.py --campaign comeback --limit 200

Production (Railway)::

    railway run python backend/scripts/send_push_campaign.py --campaign daily

Zamanlama: Railway'de "Cron" servisi ya da harici bir cron ile:
    0 9  * * *  → daily     (12:00 TRT = 09:00 UTC)
    0 17 * * *  → streak     (20:00 TRT = 17:00 UTC)
    0 15 * * 6  → comeback   (18:00 TRT Cumartesi = 15:00 UTC)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# ``import app...`` her yerden çalışsın.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import async_session_factory  # noqa: E402
from app.services import push_campaign_service, push_service  # noqa: E402


async def _run(campaign: str, *, dry_run: bool, limit: int | None, force: bool) -> int:
    """Kampanyayı çalıştırır. Dönen değer: süreç çıkış kodu (0 = başarı)."""
    copy = push_campaign_service.CAMPAIGNS[campaign]

    # Sessiz saat kontrolü — dry-run'da engellemez (hedefleri gece de görebilelim).
    quiet = push_service.is_quiet_hours()
    if quiet and not dry_run and not force:
        print("⏰ Sessiz saat (23:00–10:00 TRT) — gönderim yapılmadı. Çıkılıyor.")
        return 0

    async with async_session_factory() as db:
        targets = await push_campaign_service.select_targets(db, campaign)
        if limit is not None:
            targets = targets[:limit]

        print(f"📣 Kampanya : {campaign}")
        print(f"   Başlık   : {copy['title']}")
        print(f"   Gövde    : {copy['body']}")
        print(f"   Hedef    : {len(targets)} kullanıcı (cihaz token'ı olanlar)")
        print(f"   Push     : {'AÇIK' if push_service.is_configured() else 'KAPALI (kimlik bilgisi yok)'}")

        if dry_run:
            print("🧪 --dry-run → gönderim YOK. İlk 10 hedef:")
            for uid in targets[:10]:
                print(f"     - {uid}")
            return 0

        if not targets:
            print("ℹ️  Hedef yok — gönderim yapılmadı.")
            return 0

        stats = await push_service.send_to_users(
            db,
            targets,
            title=copy["title"],
            body=copy["body"],
            data=copy["data"],
            # --force yalnızca sessiz saat korumasını atlar (acil duyuru); günlük
            # 1-push limiti HER ZAMAN geçerlidir (spam koruması pazarlığa açık değil).
            respect_quiet_hours=not force,
        )
        await db.commit()

    print("\n📊 Sonuç")
    print(f"   Gönderilen  : {stats['sent']}")
    print(f"   Token'sız   : {stats['no_token']}")
    print(f"   Limit dolu  : {stats['capped']} (bugün zaten push aldı)")
    print(f"   Geçersiz    : {stats['invalid']} (token silindi)")
    print(f"   Hata        : {stats['error']}")
    if stats["disabled"]:
        print("   ⚠️  Push devre dışı: FIREBASE_SERVICE_ACCOUNT_JSON tanımlı değil.")
    if stats["quiet_hours"]:
        print("   ⏰ Sessiz saat nedeniyle gönderilmedi.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retention push kampanyası gönder (streak / daily / comeback).",
    )
    parser.add_argument(
        "--campaign",
        required=True,
        choices=sorted(push_campaign_service.CAMPAIGNS.keys()),
        help="Gönderilecek kampanya.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Yalnızca hedef kitleyi listele, gönderim yapma.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="En fazla bu kadar kullanıcıya gönder (kademeli açılış için).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sessiz saat korumasını atla (acil duyuru). Günlük 1-push limiti yine geçerli.",
    )
    args = parser.parse_args()

    code = asyncio.run(
        _run(args.campaign, dry_run=args.dry_run, limit=args.limit, force=args.force)
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
