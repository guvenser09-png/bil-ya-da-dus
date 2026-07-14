"""Sıra tahmini ucu (GET /api/leaderboard/projection) testleri.

MİSAFİR DÖNÜŞÜMÜ: misafirler liderlik tablolarında gizli olduğundan puanları
birikir ama görünmez. Bu uç "bu puanla kaçıncı olurdun"u hesaplar; maç sonu ve
sıralama ekranındaki kayıt daveti kaybı bu sayıyla somutlaştırır.

Kapsam:
  • all_time: yalnızca GÖRÜNEN (misafir olmayan) oyuncular sayılır.
  • score verilmezse oyuncunun KENDİ puanı kullanılır.
  • günlük: Redis sorted set'ten okunur; misafir rakipler sayıma girmez ve
    sorguyu yapanın kendi üyeliği "üstümdekiler"e dâhil edilmez.
  • puan 0/yok → would_be_rank=null (mobil sade metne düşer).
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.api.leaderboard import _today_key
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import test_session_factory as session_factory


async def _mk_user(db, *, is_guest=False, total_score=0, games_played=1) -> User:
    u = User(
        id=uuid.uuid4(),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@t.co",
        password_hash="x",
        display_name="Test",
        avatar_id="default_01",
        is_guest=is_guest,
        total_score=total_score,
        games_played=games_played,
    )
    db.add(u)
    await db.flush()
    return u


class _FakeRedis:
    """Yalnızca zrevrange bilen küçük sahte Redis (dönem sorted set'i)."""

    def __init__(self, zsets: dict[str, dict[str, float]]):
        self._zsets = zsets

    async def zrevrange(self, key, start, stop, withscores=False):
        items = sorted(self._zsets.get(key, {}).items(), key=lambda kv: -kv[1])
        end = None if stop < 0 else stop + 1
        window = items[start:end]
        return window if withscores else [m for m, _ in window]


def _patch_redis(zsets: dict[str, dict[str, float]]):
    """Yalnızca leaderboard modülünün get_redis'ini sahte Redis'e bağlar."""
    return patch(
        "app.api.leaderboard.get_redis",
        AsyncMock(return_value=_FakeRedis(zsets)),
    )


class TestAllTimeProjection:
    """Tüm zamanlar tahmini — saf DB üzerinden."""

    @pytest.mark.asyncio
    async def test_only_visible_players_are_counted(self, client):
        """Misafir rakipler (puanları yüksek olsa da) sayıma girmez."""
        async with session_factory() as db:
            await _mk_user(db, total_score=900)  # görünen, benden üstte
            await _mk_user(db, total_score=500)  # görünen, benden altta
            await _mk_user(db, is_guest=True, total_score=800)  # misafir → sayılmaz
            guest = await _mk_user(db, is_guest=True, total_score=600)
            await db.commit()
            guest_id = str(guest.id)

        resp = await client.get(
            "/api/leaderboard/projection",
            params={"period": "all_time", "score": 600},
            headers={"Authorization": f"Bearer {create_access_token(guest_id)}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Sadece 900'lük görünen oyuncu üstte → 2. olurdu (misafir 800 sayılmaz).
        assert data["would_be_rank"] == 2
        assert data["ranked_total"] == 2  # görünen oyuncu sayısı
        assert data["is_guest"] is True
        assert data["score"] == 600

    @pytest.mark.asyncio
    async def test_uses_own_score_when_score_omitted(self, client):
        """score verilmezse misafirin KENDİ total_score'u kullanılır."""
        async with session_factory() as db:
            await _mk_user(db, total_score=900)
            guest = await _mk_user(db, is_guest=True, total_score=600)
            await db.commit()
            guest_id = str(guest.id)

        resp = await client.get(
            "/api/leaderboard/projection",
            params={"period": "all_time"},
            headers={"Authorization": f"Bearer {create_access_token(guest_id)}"},
        )
        data = resp.json()
        assert data["score"] == 600
        assert data["would_be_rank"] == 2

    @pytest.mark.asyncio
    async def test_own_score_does_not_outrank_self(self, client):
        """Kayıtlı oyuncu kendi puanını sorarsa kendini geçmiş SAYILMAZ (1. kalır)."""
        async with session_factory() as db:
            me = await _mk_user(db, total_score=500)
            await _mk_user(db, total_score=300)
            await db.commit()
            me_id = str(me.id)

        resp = await client.get(
            "/api/leaderboard/projection",
            params={"period": "all_time"},
            headers={"Authorization": f"Bearer {create_access_token(me_id)}"},
        )
        data = resp.json()
        assert data["would_be_rank"] == 1
        assert data["is_guest"] is False

    @pytest.mark.asyncio
    async def test_zero_score_yields_null_rank(self, client):
        """Puan yoksa tahmin üretilmez (mobil sade davet metnine düşer)."""
        async with session_factory() as db:
            await _mk_user(db, total_score=900)
            guest = await _mk_user(db, is_guest=True, total_score=0)
            await db.commit()
            guest_id = str(guest.id)

        resp = await client.get(
            "/api/leaderboard/projection",
            params={"period": "all_time"},
            headers={"Authorization": f"Bearer {create_access_token(guest_id)}"},
        )
        data = resp.json()
        assert data["would_be_rank"] is None
        assert data["score"] == 0


class TestDailyProjection:
    """Günlük tahmin — Redis sorted set'inden okunur."""

    @pytest.mark.asyncio
    async def test_guest_daily_score_projected_against_visible_players(self, client):
        """Misafirin BİRİKMİŞ günlük puanı, yalnızca görünen rakiplerle kıyaslanır."""
        async with session_factory() as db:
            top = await _mk_user(db, total_score=0)          # günlük 900 → üstte
            low = await _mk_user(db, total_score=0)          # günlük 300 → altta
            rival_guest = await _mk_user(db, is_guest=True)  # günlük 800 → sayılmaz
            guest = await _mk_user(db, is_guest=True)        # günlük 400 → ben
            await db.commit()
            top_id, low_id = str(top.id), str(low.id)
            rival_id, guest_id = str(rival_guest.id), str(guest.id)

        zsets = {
            _today_key(): {
                top_id: 900.0,
                rival_id: 800.0,
                guest_id: 400.0,
                low_id: 300.0,
            }
        }
        with _patch_redis(zsets):
            resp = await client.get(
                "/api/leaderboard/projection",
                params={"period": "daily"},
                headers={"Authorization": f"Bearer {create_access_token(guest_id)}"},
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["score"] == 400          # kendi birikmiş günlük puanı
        assert data["would_be_rank"] == 2    # sadece 900'lük görünen oyuncu üstte
        assert data["ranked_total"] == 2     # görünen oyuncu sayısı (top + low)
        assert data["is_guest"] is True

    @pytest.mark.asyncio
    async def test_explicit_score_overrides_redis_score(self, client):
        """score verilirse (ör. tek maçın puanı) Redis'teki birikim yerine o kullanılır."""
        async with session_factory() as db:
            top = await _mk_user(db)
            guest = await _mk_user(db, is_guest=True)
            await db.commit()
            top_id, guest_id = str(top.id), str(guest.id)

        zsets = {_today_key(): {top_id: 900.0, guest_id: 400.0}}
        with _patch_redis(zsets):
            resp = await client.get(
                "/api/leaderboard/projection",
                params={"period": "daily", "score": 1000},
                headers={"Authorization": f"Bearer {create_access_token(guest_id)}"},
            )
        data = resp.json()
        assert data["score"] == 1000
        assert data["would_be_rank"] == 1  # 900'ü geçerdi

    @pytest.mark.asyncio
    async def test_redis_unavailable_returns_null_rank(self, client):
        """Redis okunamazsa tahmin üretilmez ama uç 200 döner (oyunu bozma)."""
        async with session_factory() as db:
            guest = await _mk_user(db, is_guest=True)
            await db.commit()
            guest_id = str(guest.id)

        with patch("app.api.leaderboard.get_redis", AsyncMock(side_effect=RuntimeError)):
            resp = await client.get(
                "/api/leaderboard/projection",
                params={"period": "daily"},
                headers={"Authorization": f"Bearer {create_access_token(guest_id)}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["would_be_rank"] is None
        assert data["ranked_total"] == 0

    @pytest.mark.asyncio
    async def test_invalid_period_rejected(self, client):
        """Desteklenmeyen dönem 422 döner (season/friends tahmini yok)."""
        resp = await client.get(
            "/api/leaderboard/projection", params={"period": "season"}
        )
        assert resp.status_code == 422
