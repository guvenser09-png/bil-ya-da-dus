"""Leaderboard endpoints — daily, weekly, all-time, friends rankings.

Puanlar oyun bitince KALICI kaydedilir (User.total_score birikimli + Redis
günlük/haftalık sorted set). Bu uçlar o veriyi okuyup isim/avatar/puan ile
döndürür. "Çok oynayan çok puan toplar" → all_time = User.total_score.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.redis_client import get_redis
from app.utils.security import decode_token

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    rank: int,
    user: User,
    score: int | None = None,
    points_to_next: int | None = None,
) -> dict:
    """Mobil leaderboard'un beklediği biçimde tek satır.

    points_to_next: bir üstteki oyuncunun skoru − bu oyuncunun skoru. Rank 1
    (en tepe) ise None. Mobil bunu "lider olmana N puan kaldı" için okur.
    """
    return {
        "rank": rank,
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name or user.username,
        "avatar_id": user.avatar_id,
        "score": int(score if score is not None else user.total_score),
        "total_score": user.total_score,
        "games_won": user.games_won,
        "games_played": user.games_played,
        "win_rate": user.win_rate,
        "level": user.level,
        "points_to_next": points_to_next,
        # Kuşanılmış kozmetikler (mobil zirvedekilerin kozmetiğini gösterir).
        # ws/game.py oyuncu objesiyle BİREBİR aynı anahtarlar: frame/name_color/effect.
        # User satırları zaten tek sorguyla (all_time/friends select, redis IN(...))
        # çekildiği için bu alanlar ek sorgu (N+1) doğurmaz.
        "frame": user.equipped_frame,
        "name_color": user.equipped_name_color,
        "effect": user.equipped_effect,
    }


def _optional_user_id(request: Request) -> str | None:
    """Authorization başlığından (varsa) kullanıcı id'sini çöz; yoksa None."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = decode_token(auth[7:], expected_type="access")
        return payload.get("sub")
    except Exception:
        return None


def _today_key() -> str:
    return f"leaderboard:daily:{datetime.now(timezone.utc).strftime('%Y%m%d')}"


def _week_key() -> str:
    iso = datetime.now(timezone.utc).isocalendar()
    return f"leaderboard:weekly:{iso[0]}W{iso[1]:02d}"


def _days_left_in_week() -> int:
    # Pazar gününe kadar kalan gün (haftalık sezon geri sayımı için).
    return 7 - datetime.now(timezone.utc).isoweekday()


async def _alltime_entries(db: AsyncSession, limit: int) -> list[dict]:
    stmt = (
        select(User)
        .where(
            and_(
                User.is_active == True,  # noqa: E712
                User.games_played > 0,
                User.deleted_at.is_(None),  # HATA 4: silinmiş hesapları gizle
            )
        )
        # HATA 2a: deterministik tie-breaker (User.id.asc) → sıra çağrılar arası sabit.
        .order_by(User.total_score.desc(), User.games_won.desc(), User.id.asc())
        .limit(limit)
    )
    users = (await db.execute(stmt)).scalars().all()
    # HATA 3: liste entry'lerine points_to_next ekle (bir üstteki - kendi skoru).
    entries: list[dict] = []
    for i, u in enumerate(users):
        ptn = None if i == 0 else int(users[i - 1].total_score - u.total_score)
        entries.append(_entry(i + 1, u, points_to_next=ptn))
    return entries


async def _redis_period_entries(db: AsyncSession, key: str, limit: int) -> list[dict] | None:
    """Redis sorted set'ten (günlük/haftalık) sıralama; DB'den isim/avatar ekler.

    Set boş/erişilemezse None döner (çağıran all_time'a düşebilir).
    """
    try:
        redis = await get_redis()
        rows = await redis.zrevrange(key, 0, limit - 1, withscores=True)
    except Exception:
        return None
    if not rows:
        return None

    # user_id string -> UUID; geçersizleri atla.
    uuids = []
    score_by_id: dict[str, float] = {}
    order: list[str] = []
    for uid, score in rows:
        try:
            uuids.append(uuid.UUID(uid))
        except (ValueError, AttributeError):
            continue
        score_by_id[uid] = score
        order.append(uid)

    if not uuids:
        return None

    users = (
        await db.execute(select(User).where(User.id.in_(uuids)))
    ).scalars().all()
    by_id = {str(u.id): u for u in users}

    entries: list[dict] = []
    rank = 1
    prev_score: int | None = None
    for uid in order:
        u = by_id.get(uid)
        if u is None:
            continue
        cur_score = int(score_by_id[uid])
        # HATA 3: bir üstteki oyuncunun dönem skoru − bu oyuncunun skoru.
        ptn = None if prev_score is None else int(prev_score - cur_score)
        entries.append(_entry(rank, u, score=cur_score, points_to_next=ptn))
        prev_score = cur_score
        rank += 1
    return entries


async def _my_alltime_entry(db: AsyncSession, user_id: str) -> dict | None:
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        return None
    me = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if me is None:
        return None
    # HATA 2b: rank, listeyle BİREBİR aynı composite ölçütle hesaplanır
    # (total_score, games_won, id). Böylece eşit skorlu kullanıcılarda liste
    # rank'i ile my_entry rank'i çelişmez.
    higher_stmt = (
        select(func.count())
        .select_from(User)
        .where(
            User.is_active == True,  # noqa: E712
            User.games_played > 0,
            User.deleted_at.is_(None),  # HATA 4
            or_(
                User.total_score > me.total_score,
                and_(
                    User.total_score == me.total_score,
                    User.games_won > me.games_won,
                ),
                and_(
                    User.total_score == me.total_score,
                    User.games_won == me.games_won,
                    User.id < me.id,
                ),
            ),
        )
    )
    higher = (await db.scalar(higher_stmt)) or 0
    rank = int(higher) + 1

    # HATA 3: points_to_next = bir üstteki oyuncunun (aynı sıralamada rank-1)
    # total_score'u − benim skorum. Rank 1 ise None.
    points_to_next = None
    if rank > 1:
        prev_stmt = (
            select(User.total_score)
            .where(
                User.is_active == True,  # noqa: E712
                User.games_played > 0,
                User.deleted_at.is_(None),
                or_(
                    User.total_score > me.total_score,
                    and_(
                        User.total_score == me.total_score,
                        User.games_won > me.games_won,
                    ),
                    and_(
                        User.total_score == me.total_score,
                        User.games_won == me.games_won,
                        User.id < me.id,
                    ),
                ),
            )
            # En düşük "benden üstte" olan = tam bir üstümdeki oyuncu.
            .order_by(User.total_score.asc(), User.games_won.asc(), User.id.desc())
            .limit(1)
        )
        prev_score = await db.scalar(prev_stmt)
        if prev_score is not None:
            points_to_next = int(prev_score - me.total_score)

    return _entry(rank, me, points_to_next=points_to_next)


async def _my_redis_entry(db: AsyncSession, key: str, user_id: str) -> dict | None:
    points_to_next: int | None = None
    try:
        redis = await get_redis()
        score = await redis.zscore(key, user_id)
        if score is None:
            return None
        rank = await redis.zrevrank(key, user_id)
        # HATA 3: bir üstteki oyuncunun dönem skoru − benim skorum (rank 1 ise None).
        if rank and rank > 0:
            above = await redis.zrevrange(key, rank - 1, rank - 1, withscores=True)
            if above:
                points_to_next = int(above[0][1] - score)
    except Exception:
        return None
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        return None
    me = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if me is None:
        return None
    return _entry((rank or 0) + 1, me, score=int(score), points_to_next=points_to_next)


# ---------------------------------------------------------------------------
# Endpoints  (mobil: /api/leaderboard/{daily|weekly|all_time|friends})
# ---------------------------------------------------------------------------

@router.get("/all_time")
async def get_all_time(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Tüm zamanlar — birikimli toplam puana göre (çok oynayan üste çıkar)."""
    entries = await _alltime_entries(db, limit)
    my_entry = None
    uid = _optional_user_id(request)
    if uid:
        my_entry = await _my_alltime_entry(db, uid)
    return {"period": "all_time", "entries": entries, "my_entry": my_entry, "total": len(entries)}


@router.get("/daily")
async def get_daily(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Bugün kazanılan puana göre sıralama (Redis); boşsa tüm zamanlara düşer."""
    entries = await _redis_period_entries(db, _today_key(), limit)
    period = "daily"
    if entries is None:
        entries = await _alltime_entries(db, limit)
        period = "daily_fallback_all_time"
    my_entry = None
    uid = _optional_user_id(request)
    if uid:
        # HATA 1: günlük skor yoksa my_entry None kalır. all-time skor/rank'i
        # "günlük" gibi göstermek YANLIŞTI (hiç oynamadığı gün "1.'sin" gibi).
        my_entry = await _my_redis_entry(db, _today_key(), uid)
    return {"period": period, "entries": entries, "my_entry": my_entry, "total": len(entries)}


@router.get("/weekly")
async def get_weekly(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Bu hafta kazanılan puana göre sıralama (Redis); boşsa tüm zamanlara düşer."""
    entries = await _redis_period_entries(db, _week_key(), limit)
    period = "weekly"
    if entries is None:
        entries = await _alltime_entries(db, limit)
        period = "weekly_fallback_all_time"
    my_entry = None
    uid = _optional_user_id(request)
    if uid:
        # HATA 1: haftalık skor yoksa my_entry None kalır (all-time'a düşmez).
        my_entry = await _my_redis_entry(db, _week_key(), uid)
    return {
        "period": period,
        "entries": entries,
        "my_entry": my_entry,
        "season_days_left": _days_left_in_week(),
        "total": len(entries),
    }


@router.get("/season")
async def get_season(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Aylık ranked sezon sıralaması (turnuva 3x + normal maç puanları toplamı).

    Sezon = ayın ilk-pazartesisinden sonraki ayın ilk-pazartesisine kadar.
    Sezon sonunda sıfırlanır (season_id'li puan saklama). my_entry: rank, puan,
    points_to_next; ayrıca season_id + season_end (geri sayım) döner.
    """
    from app.services.tournament_service import TournamentService

    uid = _optional_user_id(request)
    return await TournamentService.leaderboard(db, user_id=uid, limit=limit)


@router.get("/friends")
async def get_friends(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Arkadaş sıralaması — yalnızca kabul edilmiş arkadaşlar + kullanıcının
    kendisi, total_score'a göre sıralı.

    Giriş yapılmamışsa boş liste döner (arkadaş grafiği kişiye özeldir).
    """
    uid = _optional_user_id(request)
    if not uid:
        return {"period": "friends", "entries": [], "my_entry": None, "total": 0}

    try:
        me_uuid = uuid.UUID(uid)
    except (ValueError, AttributeError):
        return {"period": "friends", "entries": [], "my_entry": None, "total": 0}

    # Arkadaş id'leri + kendisi.
    from app.services.friend_service import FriendService

    friend_ids = await FriendService.accepted_friend_ids(db, uid)
    circle_ids = list({me_uuid, *friend_ids})

    stmt = (
        select(User)
        .where(
            and_(
                User.id.in_(circle_ids),
                User.is_active == True,  # noqa: E712
                User.deleted_at.is_(None),
            )
        )
        # HATA 2a: deterministik tie-breaker.
        .order_by(User.total_score.desc(), User.games_won.desc(), User.id.asc())
        .limit(limit)
    )
    users = (await db.execute(stmt)).scalars().all()
    # HATA 3: points_to_next ekle (bir üstteki - kendi skoru).
    entries = []
    for i, u in enumerate(users):
        ptn = None if i == 0 else int(users[i - 1].total_score - u.total_score)
        entries.append(_entry(i + 1, u, points_to_next=ptn))

    my_entry = next((e for e in entries if e["user_id"] == uid), None)
    return {
        "period": "friends",
        "entries": entries,
        "my_entry": my_entry,
        "total": len(entries),
    }
