"""Arkadaş servisi — istek gönderme/kabul/red, listeleme, arama.

ÖNEMLİ TASARIM NOTU
-------------------
Mevcut `Friendship` modelinde (app/models/friendship.py) bir `status`
(pending/accepted) alanı YOK. Tablo `user1_id`, `user2_id`, `level`,
`games_together`, `created_at` kolonlarından oluşuyor ve migrate edilmiş
durumda. Bu serviste model/migration DEĞİŞTİRİLMEDİĞİ için, "bekleyen istek"
durumunu şema değişikliği yapmadan kodlamak gerekti.

Kullanılan konvansiyon (şema değişmeden, veriyi bozmadan):
- BEKLEYEN İSTEK (pending): yönlü satır → `user1_id` = isteği GÖNDEREN,
  `user2_id` = isteği ALAN. Ayırt etmek için sentinel: `games_together = -1`.
- KABUL EDİLMİŞ ARKADAŞLIK (accepted): tek satır, sıralı çift
  (user1_id = min(uuid), user2_id = max(uuid)) ve `games_together >= 0`.
  Böylece gerçek "birlikte oynanan oyun" sayacı 0'dan başlar (uq_friendship_pair
  ihlali olmaması için kabul anında satır kanonik çifte dönüştürülür).

Bu, modele status alanı eklenene kadar geçerli bir ara çözümdür. Status alanı
eklenirse bu sentinel mantığı kaldırılıp gerçek alanla değiştirilmelidir.
"""

import logging
import uuid as uuid_mod

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendship import Friendship, FriendshipLevel
from app.models.user import User

logger = logging.getLogger("app.friend_service")

# Bekleyen isteği ayırt eden sentinel (games_together).
PENDING_SENTINEL = -1
SEARCH_LIMIT = 20


def _to_uuid(user_id) -> uuid_mod.UUID:
    """String/UUID -> UUID (user_service ile aynı desen)."""
    if isinstance(user_id, uuid_mod.UUID):
        return user_id
    return uuid_mod.UUID(str(user_id))


def _ordered_pair(a: uuid_mod.UUID, b: uuid_mod.UUID) -> tuple[uuid_mod.UUID, uuid_mod.UUID]:
    """Kabul edilmiş arkadaşlık için kanonik (sıralı) çift."""
    return (a, b) if str(a) <= str(b) else (b, a)


def _is_pending(f: Friendship) -> bool:
    return f.games_together == PENDING_SENTINEL


def _is_accepted(f: Friendship) -> bool:
    return f.games_together != PENDING_SENTINEL


def _user_public(user: User) -> dict:
    """Arkadaş listesi/istek satırı için kullanıcı özeti."""
    return {
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name or user.username,
        "avatar_id": user.avatar_id,
        "level": user.level,
        "total_score": user.total_score,
        "is_premium": user.is_premium,
    }


class FriendService:
    """Arkadaşlık iş mantığı (mevcut Friendship modelini kullanır)."""

    # --- Yardımcı sorgular ---

    @staticmethod
    async def _get_row_between(
        db: AsyncSession, a: uuid_mod.UUID, b: uuid_mod.UUID
    ) -> Friendship | None:
        """İki kullanıcı arasındaki (yönden bağımsız) ilk friendship satırı."""
        stmt = select(Friendship).where(
            or_(
                and_(Friendship.user1_id == a, Friendship.user2_id == b),
                and_(Friendship.user1_id == b, Friendship.user2_id == a),
            )
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    async def _get_user(db: AsyncSession, user_id: uuid_mod.UUID) -> User | None:
        return (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

    # --- Listeleme ---

    @staticmethod
    async def list_friends(db: AsyncSession, user_id: str) -> list[dict]:
        """Kabul edilmiş arkadaşları kullanıcı bilgisiyle döndür."""
        me = _to_uuid(user_id)
        stmt = select(Friendship).where(
            or_(Friendship.user1_id == me, Friendship.user2_id == me),
            Friendship.games_together != PENDING_SENTINEL,
        )
        rows = (await db.execute(stmt)).scalars().all()

        friend_ids = [
            (f.user2_id if f.user1_id == me else f.user1_id) for f in rows
        ]
        if not friend_ids:
            return []

        users = (
            await db.execute(
                select(User).where(
                    User.id.in_(friend_ids),
                    User.is_active == True,  # noqa: E712
                    User.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        return [_user_public(u) for u in users]

    @staticmethod
    async def list_requests(db: AsyncSession, user_id: str) -> dict:
        """Bekleyen istekler: gelen (incoming) + giden (outgoing)."""
        me = _to_uuid(user_id)
        stmt = select(Friendship).where(
            Friendship.games_together == PENDING_SENTINEL,
            or_(Friendship.user1_id == me, Friendship.user2_id == me),
        )
        rows = (await db.execute(stmt)).scalars().all()

        incoming_ids = [f.user1_id for f in rows if f.user2_id == me]
        outgoing_ids = [f.user2_id for f in rows if f.user1_id == me]

        all_ids = list({*incoming_ids, *outgoing_ids})
        users_by_id: dict[uuid_mod.UUID, User] = {}
        if all_ids:
            users = (
                await db.execute(
                    select(User).where(
                        User.id.in_(all_ids),
                        User.is_active == True,  # noqa: E712
                        User.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            users_by_id = {u.id: u for u in users}

        incoming = [
            _user_public(users_by_id[uid]) for uid in incoming_ids if uid in users_by_id
        ]
        outgoing = [
            _user_public(users_by_id[uid]) for uid in outgoing_ids if uid in users_by_id
        ]
        return {"incoming": incoming, "outgoing": outgoing}

    @staticmethod
    async def search(db: AsyncSession, user_id: str, query: str) -> list[dict]:
        """Kullanıcı adına/görünen isme göre ara; ilişki durumunu ekle.

        status: 'none' | 'friend' | 'incoming' | 'outgoing'
        """
        me = _to_uuid(user_id)
        q = (query or "").strip()
        if not q:
            return []

        pattern = f"%{q}%"
        users = (
            await db.execute(
                select(User)
                .where(
                    or_(
                        User.username.ilike(pattern),
                        User.display_name.ilike(pattern),
                    )
                )
                .where(User.id != me)
                .where(User.is_active == True)  # noqa: E712
                .where(User.is_banned == False)  # noqa: E712
                .where(User.deleted_at.is_(None))
                .order_by(User.games_played.desc())
                .limit(SEARCH_LIMIT)
            )
        ).scalars().all()
        if not users:
            return []

        # İlişki durumlarını tek sorguda topla.
        other_ids = [u.id for u in users]
        rels = (
            await db.execute(
                select(Friendship).where(
                    or_(
                        and_(Friendship.user1_id == me, Friendship.user2_id.in_(other_ids)),
                        and_(Friendship.user2_id == me, Friendship.user1_id.in_(other_ids)),
                    )
                )
            )
        ).scalars().all()

        status_by_id: dict[uuid_mod.UUID, str] = {}
        for f in rels:
            other = f.user2_id if f.user1_id == me else f.user1_id
            if _is_accepted(f):
                status_by_id[other] = "friend"
            elif f.user1_id == me:
                status_by_id[other] = "outgoing"
            else:
                status_by_id[other] = "incoming"

        result = []
        for u in users:
            result.append(
                {
                    "user_id": str(u.id),
                    "username": u.username,
                    "display_name": u.display_name or u.username,
                    "avatar_id": u.avatar_id,
                    "status": status_by_id.get(u.id, "none"),
                }
            )
        return result

    # --- Mutasyonlar ---

    @staticmethod
    async def send_request(db: AsyncSession, user_id: str, target_id: str) -> dict:
        """Arkadaşlık isteği gönder.

        - Kendine istek atılamaz.
        - Hedef yoksa/banlı/silinmişse hata.
        - Zaten arkadaşsa: idempotent ('already_friends').
        - Zaten giden istek varsa: idempotent ('already_requested').
        - Karşı taraf zaten SANA istek attıysa: OTOMATİK karşılıklı kabul.
        """
        me = _to_uuid(user_id)
        other = _to_uuid(target_id)
        if me == other:
            raise ValueError("Kendinize arkadaşlık isteği gönderemezsiniz.")

        target = await FriendService._get_user(db, other)
        if (
            target is None
            or not target.is_active
            or target.is_banned
            or target.deleted_at is not None
        ):
            raise ValueError("Kullanıcı bulunamadı.")

        existing = await FriendService._get_row_between(db, me, other)
        if existing is not None:
            if _is_accepted(existing):
                return {"status": "already_friends"}
            # Bekleyen istek mevcut.
            if existing.user1_id == me:
                # Zaten ben göndermişim → idempotent.
                return {"status": "already_requested"}
            # Karşı taraf bana göndermiş → OTOMATİK karşılıklı kabul.
            a, b = _ordered_pair(me, other)
            existing.user1_id = a
            existing.user2_id = b
            existing.games_together = 0
            existing.level = FriendshipLevel.TANIDIK
            await db.flush()
            return {"status": "accepted"}

        # Hiç ilişki yok → yeni bekleyen istek (yönlü: me -> other).
        friendship = Friendship(
            user1_id=me,
            user2_id=other,
            games_together=PENDING_SENTINEL,
            level=FriendshipLevel.TANIDIK,
        )
        db.add(friendship)
        await db.flush()
        return {"status": "requested"}

    @staticmethod
    async def accept_request(db: AsyncSession, user_id: str, requester_id: str) -> dict:
        """Gelen bir isteği kabul et (requester -> me yönlü pending)."""
        me = _to_uuid(user_id)
        other = _to_uuid(requester_id)
        if me == other:
            raise ValueError("Geçersiz işlem.")

        existing = await FriendService._get_row_between(db, me, other)
        if existing is None:
            raise ValueError("Bekleyen bir istek bulunamadı.")
        if _is_accepted(existing):
            return {"status": "already_friends"}
        if existing.user2_id != me:
            # İsteği ben göndermişim; ben kabul edemem.
            raise ValueError("Bu isteği kabul edemezsiniz.")

        a, b = _ordered_pair(me, other)
        existing.user1_id = a
        existing.user2_id = b
        existing.games_together = 0
        existing.level = FriendshipLevel.TANIDIK
        await db.flush()
        return {"status": "accepted"}

    @staticmethod
    async def reject_request(db: AsyncSession, user_id: str, requester_id: str) -> dict:
        """Gelen isteği reddet/sil (bekleyen satırı kaldır)."""
        me = _to_uuid(user_id)
        other = _to_uuid(requester_id)

        existing = await FriendService._get_row_between(db, me, other)
        if existing is None or _is_accepted(existing):
            raise ValueError("Bekleyen bir istek bulunamadı.")
        await db.delete(existing)
        await db.flush()
        return {"status": "rejected"}

    @staticmethod
    async def remove_friend(db: AsyncSession, user_id: str, friend_id: str) -> dict:
        """Arkadaşlıktan çık (kabul edilmiş satırı sil)."""
        me = _to_uuid(user_id)
        other = _to_uuid(friend_id)

        existing = await FriendService._get_row_between(db, me, other)
        if existing is None or not _is_accepted(existing):
            raise ValueError("Bu kullanıcı arkadaşınız değil.")
        await db.delete(existing)
        await db.flush()
        return {"status": "removed"}

    @staticmethod
    async def accepted_friend_ids(db: AsyncSession, user_id: str) -> list[uuid_mod.UUID]:
        """Kabul edilmiş arkadaşların UUID listesi (leaderboard için)."""
        me = _to_uuid(user_id)
        rows = (
            await db.execute(
                select(Friendship).where(
                    or_(Friendship.user1_id == me, Friendship.user2_id == me),
                    Friendship.games_together != PENDING_SENTINEL,
                )
            )
        ).scalars().all()
        return [(f.user2_id if f.user1_id == me else f.user1_id) for f in rows]
