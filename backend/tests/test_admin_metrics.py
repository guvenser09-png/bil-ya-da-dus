"""Admin analitik ucu + DAU/maç işaretleme testleri (hafif, SDK'sız analitik)."""

import uuid

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.user import User
from app.services import analytics_service


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


class TestMetricsAuth:
    """Paylaşılan-anahtar koruması."""

    @pytest.mark.asyncio
    async def test_forbidden_when_key_not_configured(self, client: AsyncClient, monkeypatch):
        """Anahtar boşsa (özellik kapalı) her istek 403."""
        monkeypatch.setattr(settings, "ADMIN_METRICS_KEY", "")
        # anahtarla da anahtarsız da 403
        assert (await client.get("/api/admin/metrics?key=whatever")).status_code == 403
        assert (await client.get("/api/admin/metrics")).status_code == 403

    @pytest.mark.asyncio
    async def test_forbidden_with_wrong_key(self, client: AsyncClient, monkeypatch):
        """Yapılandırılmış anahtar varken yanlış anahtar 403."""
        monkeypatch.setattr(settings, "ADMIN_METRICS_KEY", "s3cret")
        assert (await client.get("/api/admin/metrics?key=nope")).status_code == 403

    @pytest.mark.asyncio
    async def test_ok_with_correct_key(self, client: AsyncClient, monkeypatch):
        """Doğru anahtarla 200 + beklenen JSON yapısı."""
        monkeypatch.setattr(settings, "ADMIN_METRICS_KEY", "s3cret")
        await _register(client, "metricuser1")
        await _register(client, "metricuser2")

        resp = await client.get("/api/admin/metrics?key=s3cret")
        assert resp.status_code == 200
        data = resp.json()
        # Üst düzey anahtarlar
        assert set(data.keys()) >= {
            "generated_at", "users", "new_users", "daily", "retention", "redis_available",
        }
        assert data["users"]["total"] == 2
        assert data["users"]["registered"] == 2
        assert data["users"]["guest"] == 0
        # Yeni kayıtlar bugün oluştu → hepsi son 1/7/30 günde
        assert data["new_users"]["last_1d"] == 2
        assert data["new_users"]["last_30d"] == 2
        # 7 günlük seri (en yeni gün önce)
        assert len(data["daily"]) == 7
        assert data["redis_available"] is True


class TestUserBreakdown:
    """Kayıtlı vs misafir ayrımı."""

    @pytest.mark.asyncio
    async def test_guest_vs_registered(self, client: AsyncClient, db_session, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_METRICS_KEY", "k")
        await _register(client, "realuser")
        # Misafir kullanıcı doğrudan DB'ye ekle
        guest = User(id=uuid.uuid4(), username="guest_dev_1", is_guest=True)
        db_session.add(guest)
        await db_session.commit()

        data = (await client.get("/api/admin/metrics?key=k")).json()
        assert data["users"]["total"] == 2
        assert data["users"]["guest"] == 1
        assert data["users"]["registered"] == 1


class TestDauMarking:
    """Auth dependency DAU işaretlemesi."""

    @pytest.mark.asyncio
    async def test_authenticated_request_marks_dau(self, client: AsyncClient, monkeypatch, mock_redis):
        """Kimlik doğrulanmış bir istek kullanıcıyı bugünün DAU setine ekler."""
        monkeypatch.setattr(settings, "ADMIN_METRICS_KEY", "k")
        token, user = await _register(client, "dauuser")

        # Kayıt (register) get_current_user_id'den GEÇMEZ → henüz DAU yok
        today_key = analytics_service.dau_key(
            analytics_service._day_str(analytics_service._utc_date())
        )
        assert await mock_redis.scard(today_key) == 0

        # Auth'lu bir uç (get_current_user_id tetiklenir → mark_daily_active)
        me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200

        # Kullanıcı artık bugünün DAU setinde
        members = await mock_redis.smembers(today_key)
        assert user["id"] in members

        # Uç üzerinden de görünür (bugünkü dau >= 1)
        data = (await client.get("/api/admin/metrics?key=k")).json()
        assert data["daily"][0]["dau"] >= 1


class TestMatchCount:
    """Günlük maç sayacı (INCR)."""

    @pytest.mark.asyncio
    async def test_increment_reflected_in_metrics(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_METRICS_KEY", "k")
        await analytics_service.increment_match_count()
        await analytics_service.increment_match_count()
        await analytics_service.increment_match_count()

        data = (await client.get("/api/admin/metrics?key=k")).json()
        # daily[0] = bugün
        assert data["daily"][0]["matches"] == 3
