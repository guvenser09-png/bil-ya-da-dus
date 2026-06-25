"""Aylık "ranked sezon" (sıralama sezonu) deterministik hesabı.

ÖNEMLİ — İki ayrı sezon kavramı var, karıştırma:
  1. **Battle Pass sezonu** (app/services/season_service.py): User.season_points
     üzerinde kümülatif ilerleme, tier/claim mantığı. SIFIRLANMAZ (sabit SEASON_ID).
     Burası DOKUNULMADI.
  2. **Ranked sezon** (BU MODÜL + season_scores tablosu): Aylık rekabet tablosu.
     Her ayın İLK PAZARTESİsi yeni sezon başlar, sezon sonunda sıralama SIFIRLANIR
     (yeni season_id → yeni satırlar), top sıralara ödül dağıtılır.

Sezon penceresi: bir ayın ilk-pazartesisinden, BİR SONRAKİ ayın ilk-pazartesisine
kadar (başlangıç dahil, bitiş hariç). season_id formatı sezonun BAŞLADIĞI tarihten
türetilir: "YYYY-MM" (örn. 2026 Haziran'ın ilk pazartesisinde başlayan sezon → "2026-06").

Zaman dilimi: Proje genelinde leaderboard/ödül sayaçları UTC kullanır
(match_reward_service, leaderboard.py hep UTC). Tutarlılık için ranked sezon da UTC.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def first_monday_of_month(year: int, month: int) -> date:
    """Verilen ay için ilk pazartesi gününü (date) döner."""
    d = date(year, month, 1)
    # weekday(): Pazartesi=0 ... Pazar=6. İlk pazartesiye kadar ilerle.
    offset = (7 - d.weekday()) % 7
    return d + timedelta(days=offset)


def _add_month(year: int, month: int) -> tuple[int, int]:
    """(year, month) → bir sonraki ayın (year, month)."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _prev_month(year: int, month: int) -> tuple[int, int]:
    """(year, month) → bir önceki ayın (year, month)."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def season_id_for(dt: datetime | None = None) -> str:
    """Verilen ana (UTC) denk gelen ranked sezonun id'sini döner ("YYYY-MM").

    Sezon, içinde bulunduğumuz ayın ilk-pazartesisinde başlar. Ancak ayın
    ilk-pazartesisinden ÖNCEYSEK (örn. ayın 1'i Salı ise 1-7 arası), hâlâ
    BİR ÖNCEKİ ayın ilk-pazartesisinde başlayan sezondayız.
    """
    now = (dt or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today = now.date()
    fm = first_monday_of_month(today.year, today.month)
    if today >= fm:
        y, m = today.year, today.month
    else:
        # Bu ayın ilk pazartesisinden önce → önceki ayın sezonundayız.
        y, m = _prev_month(today.year, today.month)
    return f"{y:04d}-{m:02d}"


def season_bounds(season_id: str) -> tuple[datetime, datetime]:
    """season_id ("YYYY-MM") için (başlangıç, bitiş) UTC datetime döner.

    Başlangıç: o ayın ilk-pazartesisi 00:00 UTC (dahil).
    Bitiş: BİR SONRAKİ ayın ilk-pazartesisi 00:00 UTC (hariç).
    """
    year, month = (int(x) for x in season_id.split("-"))
    start_d = first_monday_of_month(year, month)
    ny, nm = _add_month(year, month)
    end_d = first_monday_of_month(ny, nm)
    start = datetime(start_d.year, start_d.month, start_d.day, tzinfo=timezone.utc)
    end = datetime(end_d.year, end_d.month, end_d.day, tzinfo=timezone.utc)
    return start, end


def current_season(dt: datetime | None = None) -> dict:
    """Mevcut ranked sezonun özetini döner.

    Returns:
        {
          "season_id": "2026-06",
          "season_start": ISO8601,
          "season_end": ISO8601,           # bir sonraki sezonun başı
          "seconds_left": int,             # şu andan bitişe kalan saniye
          "time_left_days": int,           # kabaca kalan gün (geri sayım UI)
        }
    """
    now = (dt or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sid = season_id_for(now)
    start, end = season_bounds(sid)
    seconds_left = max(0, int((end - now).total_seconds()))
    return {
        "season_id": sid,
        "season_start": start.isoformat(),
        "season_end": end.isoformat(),
        "seconds_left": seconds_left,
        "time_left_days": seconds_left // 86400,
    }


def previous_season_id(season_id: str) -> str:
    """Verilen sezondan bir ÖNCEKİ ranked sezonun id'sini döner.

    "Önceki sezon" = bu sezonun başlangıcından hemen önceki an hangi sezona
    aitse o. (Aylık ilk-pazartesi mantığında bu, takvim olarak bir önceki aydır.)
    """
    start, _ = season_bounds(season_id)
    before = start - timedelta(seconds=1)
    return season_id_for(before)
