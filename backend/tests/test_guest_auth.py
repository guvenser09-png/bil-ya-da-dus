"""Misafir girişi (POST /api/auth/guest) ve hesap kalıcılaştırma
(POST /api/auth/claim) testleri.
"""

import pytest
from httpx import AsyncClient

DEVICE_ID = "test-device-0001-abcdef"


async def guest_login(client: AsyncClient, device_id: str = DEVICE_ID) -> dict:
    """Yardımcı: misafir girişi yapıp yanıt gövdesini döndür."""
    response = await client.post("/api/auth/guest", json={"device_id": device_id})
    assert response.status_code == 200, response.text
    return response.json()


class TestGuestLogin:
    """Misafir giriş ucu."""

    @pytest.mark.asyncio
    async def test_guest_creates_account(self, client: AsyncClient):
        """İlk misafir girişi otomatik hesap oluşturur ve token döndürür."""
        data = await guest_login(client)
        assert "access_token" in data
        assert "refresh_token" in data
        user = data["user"]
        assert user["is_guest"] is True
        assert user["username"].startswith("Oyuncu")
        assert user["email"] is None

    @pytest.mark.asyncio
    async def test_guest_same_device_returns_same_user(self, client: AsyncClient):
        """Aynı device_id ile ikinci giriş AYNI hesabı döndürür (yeni hesap açmaz)."""
        first = await guest_login(client)
        second = await guest_login(client)
        assert first["user"]["id"] == second["user"]["id"]
        assert first["user"]["username"] == second["user"]["username"]

    @pytest.mark.asyncio
    async def test_guest_different_devices_get_different_users(self, client: AsyncClient):
        """Farklı device_id'ler farklı hesaplar alır."""
        a = await guest_login(client, "device-aaaa-1111")
        b = await guest_login(client, "device-bbbb-2222")
        assert a["user"]["id"] != b["user"]["id"]

    @pytest.mark.asyncio
    async def test_guest_token_works_on_me_endpoint(self, client: AsyncClient):
        """Misafir token'ı ile /users/me çağrılabilir."""
        data = await guest_login(client)
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert response.status_code == 200
        assert response.json()["is_guest"] is True

    @pytest.mark.asyncio
    async def test_guest_short_device_id_rejected(self, client: AsyncClient):
        """Çok kısa device_id 422 döner."""
        response = await client.post("/api/auth/guest", json={"device_id": "abc"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_normal_register_login_unaffected(self, client: AsyncClient):
        """Misafir ucu varken normal register+login akışı aynen çalışır."""
        reg = await client.post("/api/auth/register", json={
            "username": "normaluser",
            "password": "test123abc",
            "email": "normal@example.com",
        })
        assert reg.status_code == 201
        assert reg.json()["user"]["is_guest"] is False

        login = await client.post("/api/auth/login", json={
            "username_or_email": "normaluser",
            "password": "test123abc",
        })
        assert login.status_code == 200


class TestClaimAccount:
    """Misafir hesabı kalıcılaştırma ucu."""

    @pytest.mark.asyncio
    async def test_claim_success(self, client: AsyncClient):
        """Misafir email+şifre ile hesabını kalıcılaştırır; is_guest False olur."""
        data = await guest_login(client)
        response = await client.post(
            "/api/auth/claim",
            headers={"Authorization": f"Bearer {data['access_token']}"},
            json={"email": "claimed@example.com", "password": "test123abc"},
        )
        assert response.status_code == 200, response.text
        user = response.json()
        assert user["is_guest"] is False
        assert user["email"] == "claimed@example.com"
        # İlerleme (id) korunur
        assert user["id"] == data["user"]["id"]

        # Kalıcılaştırılan hesapla artık şifreyle giriş yapılabilir
        login = await client.post("/api/auth/login", json={
            "username_or_email": "claimed@example.com",
            "password": "test123abc",
        })
        assert login.status_code == 200

    @pytest.mark.asyncio
    async def test_claim_with_new_username(self, client: AsyncClient):
        """Claim sırasında opsiyonel yeni username verilebilir."""
        data = await guest_login(client)
        response = await client.post(
            "/api/auth/claim",
            headers={"Authorization": f"Bearer {data['access_token']}"},
            json={
                "email": "renamed@example.com",
                "password": "test123abc",
                "username": "yeniisim",
            },
        )
        assert response.status_code == 200
        assert response.json()["username"] == "yeniisim"
        # GÖRÜNEN AD DÜZELTMESİ (regresyon): misafirin varsayılan display_name'i
        # "Oyuncu"dur; claim'de seçilen kullanıcı adı görünen ada da yansımalı.
        # Aksi halde kayıtlı kullanıcı lobide/sıralamada "Oyuncu" görünüyordu
        # (prod'da 10 kullanıcı etkilendi).
        assert response.json()["display_name"] == "yeniisim"

    @pytest.mark.asyncio
    async def test_claim_without_username_fixes_display_name(
        self, client: AsyncClient
    ):
        """Username verilmeden claim'de bile display_name 'Oyuncu' KALMAMALI —
        mevcut (otomatik) kullanıcı adına düşer."""
        data = await guest_login(client)
        response = await client.post(
            "/api/auth/claim",
            headers={"Authorization": f"Bearer {data['access_token']}"},
            json={"email": "noname@example.com", "password": "test123abc"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["display_name"] != "Oyuncu"
        assert body["display_name"] == body["username"]

    @pytest.mark.asyncio
    async def test_claim_email_conflict(self, client: AsyncClient):
        """Başka hesapta kayıtlı email ile claim 409 döner."""
        await client.post("/api/auth/register", json={
            "username": "emailowner",
            "password": "test123abc",
            "email": "taken@example.com",
        })
        data = await guest_login(client)
        response = await client.post(
            "/api/auth/claim",
            headers={"Authorization": f"Bearer {data['access_token']}"},
            json={"email": "taken@example.com", "password": "test123abc"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_claim_username_conflict(self, client: AsyncClient):
        """Alınmış username ile claim 409 döner."""
        await client.post("/api/auth/register", json={
            "username": "nameowner",
            "password": "test123abc",
        })
        data = await guest_login(client)
        response = await client.post(
            "/api/auth/claim",
            headers={"Authorization": f"Bearer {data['access_token']}"},
            json={
                "email": "unique@example.com",
                "password": "test123abc",
                "username": "nameowner",
            },
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_claim_non_guest_rejected(self, client: AsyncClient):
        """Normal (misafir olmayan) hesap claim edilemez → 400."""
        reg = await client.post("/api/auth/register", json={
            "username": "alreadyfull",
            "password": "test123abc",
            "email": "full@example.com",
        })
        token = reg.json()["access_token"]
        response = await client.post(
            "/api/auth/claim",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "other@example.com", "password": "test123abc"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_claim_requires_auth(self, client: AsyncClient):
        """Auth'suz claim 401/403 döner."""
        response = await client.post(
            "/api/auth/claim",
            json={"email": "x@example.com", "password": "test123abc"},
        )
        assert response.status_code in (401, 403)
