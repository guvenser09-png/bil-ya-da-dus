"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


class TestRegister:
    """Test user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Successful registration returns tokens and user data."""
        response = await client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "test123abc",
            "email": "test@example.com",
            "display_name": "Test User",
        })
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["user"]["username"] == "testuser"
        assert data["user"]["display_name"] == "Test User"
        assert data["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """Duplicate username returns 409."""
        await client.post("/api/auth/register", json={
            "username": "duplicate",
            "password": "test123abc",
        })
        response = await client.post("/api/auth/register", json={
            "username": "duplicate",
            "password": "test456def",
        })
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Duplicate email returns 409."""
        await client.post("/api/auth/register", json={
            "username": "user1",
            "password": "test123abc",
            "email": "same@example.com",
        })
        response = await client.post("/api/auth/register", json={
            "username": "user2",
            "password": "test456def",
            "email": "same@example.com",
        })
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Password shorter than 6 chars returns 422."""
        response = await client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "123",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_username(self, client: AsyncClient):
        """Username with special chars returns 422."""
        response = await client.post("/api/auth/register", json={
            "username": "test user!",
            "password": "test123abc",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_without_email(self, client: AsyncClient):
        """Registration without email should succeed."""
        response = await client.post("/api/auth/register", json={
            "username": "noemail_user",
            "password": "test123abc",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] is None

    @pytest.mark.asyncio
    async def test_register_numeric_only_password(self, client: AsyncClient):
        """Password with only digits returns 422."""
        response = await client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "123456",
        })
        assert response.status_code == 422


class TestLogin:
    """Test user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_with_username(self, client: AsyncClient):
        """Login with username returns tokens."""
        # Register first
        await client.post("/api/auth/register", json={
            "username": "loginuser",
            "password": "test123abc",
        })
        # Login
        response = await client.post("/api/auth/login", json={
            "username_or_email": "loginuser",
            "password": "test123abc",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "loginuser"

    @pytest.mark.asyncio
    async def test_login_with_email(self, client: AsyncClient):
        """Login with email returns tokens."""
        await client.post("/api/auth/register", json={
            "username": "emaillogin",
            "password": "test123abc",
            "email": "login@example.com",
        })
        response = await client.post("/api/auth/login", json={
            "username_or_email": "login@example.com",
            "password": "test123abc",
        })
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "emaillogin"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Wrong password returns 401."""
        await client.post("/api/auth/register", json={
            "username": "wrongpw",
            "password": "test123abc",
        })
        response = await client.post("/api/auth/login", json={
            "username_or_email": "wrongpw",
            "password": "wrong_password",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Login with non-existent user returns 401."""
        response = await client.post("/api/auth/login", json={
            "username_or_email": "ghostuser",
            "password": "test123abc",
        })
        assert response.status_code == 401


class TestLogout:
    """Test logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient):
        """Logout returns success message."""
        # Register and get token
        reg = await client.post("/api/auth/register", json={
            "username": "logoutuser",
            "password": "test123abc",
        })
        token = reg.json()["access_token"]

        # Logout
        response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_logout_without_token(self, client: AsyncClient):
        """Logout without token returns 401."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 401


class TestChangePassword:
    """Test password change endpoint."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, client: AsyncClient):
        """Password change with correct current password succeeds."""
        reg = await client.post("/api/auth/register", json={
            "username": "changepw",
            "password": "oldpass123",
        })
        token = reg.json()["access_token"]

        response = await client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "oldpass123",
                "new_password": "newpass456",
            },
        )
        assert response.status_code == 200

        # Verify login with new password works
        login = await client.post("/api/auth/login", json={
            "username_or_email": "changepw",
            "password": "newpass456",
        })
        assert login.status_code == 200

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client: AsyncClient):
        """Wrong current password returns 400."""
        reg = await client.post("/api/auth/register", json={
            "username": "changepw2",
            "password": "correct123",
        })
        token = reg.json()["access_token"]

        response = await client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "wrong_current",
                "new_password": "newpass456",
            },
        )
        assert response.status_code == 400


class TestPasswordReset:
    """Test password reset flow."""

    @pytest.mark.asyncio
    async def test_password_reset_request(self, client: AsyncClient):
        """Password reset request always returns 200 (don't leak email existence)."""
        response = await client.post("/api/auth/password-reset", json={
            "email": "nonexistent@example.com",
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_password_reset_with_existing_email(self, client: AsyncClient):
        """Password reset for existing email returns token in dev mode."""
        await client.post("/api/auth/register", json={
            "username": "resetuser",
            "password": "oldpass123",
            "email": "reset@example.com",
        })
        response = await client.post("/api/auth/password-reset", json={
            "email": "reset@example.com",
        })
        assert response.status_code == 200
        # In debug mode, token is returned in message
        data = response.json()
        assert "DEV TOKEN" in data["message"]
