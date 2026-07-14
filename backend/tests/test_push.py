"""Push bildirim altyapısı testleri.

Kapsam:
  • Kimlik bilgisi (FIREBASE_SERVICE_ACCOUNT_JSON) YOKKEN servis no-op olur,
    ASLA istisna fırlatmaz.
  • Cihaz token ucu: kayıt (upsert), silme, auth zorunluluğu, hesap silmede
    token temizliği.
  • Sessiz saat (23:00–10:00 TRT) + kişi başı günde 1 push limiti.
  • Kampanya hedef seçimi: streak / daily / comeback.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.device_token import DeviceToken
from app.models.user import User
from app.services import (
    daily_challenge_service,
    push_campaign_service,
    push_service,
)


async def _register(client: AsyncClient, username: str) -> tuple[str, dict]:
    """Yardımcı: kullanıcı kaydet, (token, user) döndür."""
    resp = await client.post("/api/auth/register", json={
        "username": username,
        "password": "test123abc",
        "email": f"{username}@example.com",
        "display_name": f"Display {username}",
    })
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    return data["access_token"], data["user"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestNoCredentialsIsNoOp:
    """Firebase kimlik bilgisi yokken hiçbir şey patlamaz."""

    @pytest.mark.asyncio
    async def test_not_configured_by_default(self, monkeypatch):
        monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
        push_service.reset_credentials_cache()
        assert push_service.is_configured() is False

    @pytest.mark.asyncio
    async def test_invalid_json_disables_push_without_raising(self, monkeypatch):
        """Bozuk JSON → istisna DEĞİL, sessizce devre dışı."""
        monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "{bozuk json")
        push_service.reset_credentials_cache()
        assert push_service.is_configured() is False

    @pytest.mark.asyncio
    async def test_send_is_noop_without_credentials(
        self, client: AsyncClient, db_session, monkeypatch
    ):
        """Kimlik yokken send_to_users: gönderim yok, istisna yok, disabled=1."""
        monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
        push_service.reset_credentials_cache()

        token, user = await _register(client, "pushnoop")
        await client.post(
            "/api/users/me/push-token",
            json={"token": "fcm-token-noop", "platform": "ios"},
            headers=_auth(token),
        )

        # Sessiz saatte takılmayalım diye gönderim anını gündüze sabitliyoruz.
        noon = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        stats = await push_service.send_to_users(
            db_session, [user["id"]], "Başlık", "Gövde", now=noon
        )
        assert stats["disabled"] == 1
        assert stats["sent"] == 0
        assert stats["skipped"] == 1

    @pytest.mark.asyncio
    async def test_send_to_tokens_is_noop_without_credentials(
        self, db_session, monkeypatch
    ):
        monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
        push_service.reset_credentials_cache()
        stats = await push_service.send_to_tokens(
            db_session, ["t1", "t2"], "Başlık", "Gövde"
        )
        assert stats == {
            "sent": 0, "invalid": 0, "error": 0, "skipped": 2, "disabled": 1
        }


class TestPushTokenEndpoint:
    """POST/DELETE /api/users/me/push-token."""

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/users/me/push-token",
            json={"token": "abc1234567", "platform": "ios"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_register_and_upsert(self, client: AsyncClient, db_session, monkeypatch):
        """Aynı token iki kez gönderilince TEK satır kalır (upsert)."""
        monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
        push_service.reset_credentials_cache()

        token, user = await _register(client, "pushuser1")

        resp = await client.post(
            "/api/users/me/push-token",
            json={"token": "fcm-abc-123", "platform": "ios"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        # Kimlik bilgisi yok → push_enabled False ama token YİNE DE saklandı.
        assert body["push_enabled"] is False

        # Aynı token tekrar (platform değişerek)
        resp = await client.post(
            "/api/users/me/push-token",
            json={"token": "fcm-abc-123", "platform": "android"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

        rows = (await db_session.execute(
            select(DeviceToken).where(DeviceToken.token == "fcm-abc-123")
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].platform == "android"
        assert str(rows[0].user_id) == user["id"]

    @pytest.mark.asyncio
    async def test_delete_token(self, client: AsyncClient, db_session):
        token, _user = await _register(client, "pushuser2")
        await client.post(
            "/api/users/me/push-token",
            json={"token": "fcm-del-token-1", "platform": "ios"},
            headers=_auth(token),
        )

        resp = await client.request(
            "DELETE",
            "/api/users/me/push-token",
            json={"token": "fcm-del-token-1", "platform": "ios"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text

        rows = (await db_session.execute(
            select(DeviceToken).where(DeviceToken.token == "fcm-del-token-1")
        )).scalars().all()
        assert rows == []

    @pytest.mark.asyncio
    async def test_delete_account_clears_tokens(self, client: AsyncClient, db_session):
        """KVKK: hesap silinince cihaz token'ları da silinir."""
        token, user = await _register(client, "pushuser3")
        await client.post(
            "/api/users/me/push-token",
            json={"token": "fcm-acc-token-1", "platform": "ios"},
            headers=_auth(token),
        )

        resp = await client.delete("/api/users/me", headers=_auth(token))
        assert resp.status_code == 200, resp.text

        rows = (await db_session.execute(
            select(DeviceToken).where(
                DeviceToken.user_id == uuid.UUID(user["id"])
            )
        )).scalars().all()
        assert rows == []


class TestQuietHoursAndDailyCap:
    """Kullanıcıyı rahatsız etmeme kuralları."""

    def test_quiet_hours_window(self):
        # 23:00 TRT → sessiz
        assert push_service.is_quiet_hours(
            datetime(2026, 7, 14, 20, 30, tzinfo=timezone.utc)  # 23:30 TRT
        ) is True
        # 09:00 TRT → sessiz (10:00'dan önce)
        assert push_service.is_quiet_hours(
            datetime(2026, 7, 14, 6, 0, tzinfo=timezone.utc)  # 09:00 TRT
        ) is True
        # 12:00 TRT → serbest
        assert push_service.is_quiet_hours(
            datetime(2026, 7, 14, 9, 0, tzinfo=timezone.utc)  # 12:00 TRT
        ) is False
        # 20:00 TRT (streak kampanyası saati) → serbest
        assert push_service.is_quiet_hours(
            datetime(2026, 7, 14, 17, 0, tzinfo=timezone.utc)  # 20:00 TRT
        ) is False

    @pytest.mark.asyncio
    async def test_quiet_hours_blocks_send(self, client: AsyncClient, db_session):
        token, user = await _register(client, "pushquiet")
        await client.post(
            "/api/users/me/push-token",
            json={"token": "fcm-quiet-token-1", "platform": "ios"},
            headers=_auth(token),
        )
        midnight_trt = datetime(2026, 7, 14, 21, 0, tzinfo=timezone.utc)  # 00:00 TRT
        stats = await push_service.send_to_users(
            db_session, [user["id"]], "Başlık", "Gövde", now=midnight_trt
        )
        assert stats["quiet_hours"] == 1
        assert stats["sent"] == 0

    @pytest.mark.asyncio
    async def test_daily_cap_one_push_per_user(self):
        """Aynı gün ikinci kez kota alınamaz; ertesi gün tekrar alınır."""
        user_id = str(uuid.uuid4())
        day1 = datetime(2026, 7, 14, 9, 0, tzinfo=timezone.utc)
        assert await push_service.try_consume_daily_quota(user_id, day1) is True
        assert await push_service.try_consume_daily_quota(user_id, day1) is False

        day2 = day1 + timedelta(days=1)
        assert await push_service.try_consume_daily_quota(user_id, day2) is True


class TestCampaignTargeting:
    """Kampanya hedef kitlesi seçimi (streak / daily / comeback)."""

    @staticmethod
    async def _user_with_token(db_session, username: str, **fields) -> User:
        user = User(id=uuid.uuid4(), username=username, **fields)
        db_session.add(user)
        await db_session.flush()
        db_session.add(DeviceToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token=f"tok-{username}",
            platform="ios",
        ))
        await db_session.commit()
        return user

    @pytest.mark.asyncio
    async def test_streak_targets_only_at_risk_users(self, db_session):
        now = datetime(2026, 7, 14, 17, 0, tzinfo=timezone.utc)  # 20:00 TRT
        yesterday = now - timedelta(days=1)

        # Serisi risk altında: dün almış, bugün almamış → HEDEF
        at_risk = await self._user_with_token(
            db_session, "streak_atrisk",
            daily_streak=5, last_daily_claim_at=yesterday,
        )
        # Bugün zaten almış → hedef DEĞİL
        await self._user_with_token(
            db_session, "streak_claimed",
            daily_streak=3, last_daily_claim_at=now,
        )
        # Serisi zaten kopmuş (3 gün önce) → hedef DEĞİL
        await self._user_with_token(
            db_session, "streak_broken",
            daily_streak=2, last_daily_claim_at=now - timedelta(days=3),
        )
        # Hiç seri yok → hedef DEĞİL
        await self._user_with_token(db_session, "streak_none", daily_streak=0)

        # Token'ı OLMAYAN, serisi riskli kullanıcı → hedef DEĞİL
        db_session.add(User(
            id=uuid.uuid4(), username="streak_notoken",
            daily_streak=9, last_daily_claim_at=yesterday,
        ))
        await db_session.commit()

        targets = await push_campaign_service.select_streak_targets(db_session, now=now)
        assert targets == [str(at_risk.id)]

    @pytest.mark.asyncio
    async def test_daily_targets_exclude_players_who_played(self, db_session, mock_redis):
        now = datetime(2026, 7, 14, 9, 0, tzinfo=timezone.utc)  # 12:00 TRT

        played = await self._user_with_token(db_session, "daily_played")
        not_played = await self._user_with_token(db_session, "daily_notplayed")
        await self._user_with_token(db_session, "daily_inactive")

        # İki kullanıcı son 7 günde aktif (DAU), üçüncüsü değil.
        from app.services import analytics_service
        await analytics_service.mark_daily_active(str(played.id), now=now)
        await analytics_service.mark_daily_active(str(not_played.id), now=now)

        # Biri bugünün Günün Sorusu'nu oynadı.
        await daily_challenge_service.mark_as_played(str(played.id))

        targets = await push_campaign_service.select_daily_targets(db_session, now=now)
        assert targets == [str(not_played.id)]

    @pytest.mark.asyncio
    async def test_comeback_targets_idle_users(self, db_session, mock_redis):
        now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)

        # 5 gündür yok → HEDEF
        idle = await self._user_with_token(
            db_session, "cb_idle", last_login_at=now - timedelta(days=5),
        )
        # Dün girmiş → hedef DEĞİL
        await self._user_with_token(
            db_session, "cb_active", last_login_at=now - timedelta(days=1),
        )
        # 60 gündür yok (çok eski) → hedef DEĞİL
        await self._user_with_token(
            db_session, "cb_ancient", last_login_at=now - timedelta(days=60),
        )

        targets = await push_campaign_service.select_comeback_targets(db_session, now=now)
        assert targets == [str(idle.id)]

    @pytest.mark.asyncio
    async def test_unknown_campaign_raises(self, db_session):
        with pytest.raises(ValueError):
            await push_campaign_service.select_targets(db_session, "yok-boyle-kampanya")
