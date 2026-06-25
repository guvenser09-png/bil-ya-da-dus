"""Tests for user profile endpoints."""

import pytest
from httpx import AsyncClient


async def register_and_get_token(client: AsyncClient, username: str = "profileuser") -> tuple[str, dict]:
    """Helper: register a user and return (token, user_data)."""
    response = await client.post("/api/auth/register", json={
        "username": username,
        "password": "test123abc",
        "email": f"{username}@example.com",
        "display_name": f"Display {username}",
    })
    data = response.json()
    return data["access_token"], data["user"]


class TestGetProfile:
    """Test profile retrieval."""

    @pytest.mark.asyncio
    async def test_get_my_profile(self, client: AsyncClient):
        """Get own profile returns full data."""
        token, user = await register_and_get_token(client, "profile1")
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "profile1"
        assert data["email"] == "profile1@example.com"
        # Yeni kullanıcı başlangıç altını (model default 1000).
        assert data["coins"] == 1000
        assert "gems" not in data

    @pytest.mark.asyncio
    async def test_get_profile_without_auth(self, client: AsyncClient):
        """Profile without auth returns 401."""
        response = await client.get("/api/users/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_other_user_profile(self, client: AsyncClient):
        """Get another user's public profile."""
        _, user = await register_and_get_token(client, "public1")
        user_id = user["id"]

        response = await client.get(f"/api/users/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "public1"
        # Private fields should not be present
        assert "email" not in data
        assert "coins" not in data


class TestUpdateProfile:
    """Test profile updates."""

    @pytest.mark.asyncio
    async def test_update_display_name(self, client: AsyncClient):
        """Update display name succeeds."""
        token, _ = await register_and_get_token(client, "update1")
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"display_name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_bio(self, client: AsyncClient):
        """Update bio succeeds."""
        token, _ = await register_and_get_token(client, "bio1")
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"bio": "Trivia severim! 🎮"},
        )
        assert response.status_code == 200
        assert response.json()["bio"] == "Trivia severim! 🎮"

    @pytest.mark.asyncio
    async def test_update_bio_profanity(self, client: AsyncClient):
        """Bio with profanity returns 400."""
        token, _ = await register_and_get_token(client, "profanity1")
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"bio": "Bu bir küfür: siktir"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_interest_tags(self, client: AsyncClient):
        """Update interest tags succeeds."""
        token, _ = await register_and_get_token(client, "tags1")
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"interest_tags": ["sinema", "spor", "müzik"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["interest_tags"] == ["sinema", "spor", "müzik"]

    @pytest.mark.asyncio
    async def test_update_too_many_tags(self, client: AsyncClient):
        """More than 5 interest tags returns 422."""
        token, _ = await register_and_get_token(client, "tags2")
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"interest_tags": ["a", "b", "c", "d", "e", "f"]},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_avatar(self, client: AsyncClient):
        """Update avatar to a valid FREE character succeeds (ownership gate)."""
        token, _ = await register_and_get_token(client, "avatar1")
        # 'alien' ücretsiz başlangıç karakteri; sahiplik kapısından geçer.
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"avatar_id": "alien"},
        )
        assert response.status_code == 200
        assert response.json()["avatar_id"] == "alien"

    @pytest.mark.asyncio
    async def test_update_invalid_avatar(self, client: AsyncClient):
        """Invalid avatar ID returns 400."""
        token, _ = await register_and_get_token(client, "avatar2")
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"avatar_id": "nonexistent_avatar"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_empty_request(self, client: AsyncClient):
        """Empty update request returns 400."""
        token, _ = await register_and_get_token(client, "empty1")
        response = await client.patch(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 400


class TestUserSearch:
    """Test user search endpoint."""

    @pytest.mark.asyncio
    async def test_search_users(self, client: AsyncClient):
        """Search finds matching users."""
        token1, _ = await register_and_get_token(client, "searchable_user")
        token2, _ = await register_and_get_token(client, "another_search")

        response = await client.get(
            "/api/users/search?q=searchable",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        usernames = [u["username"] for u in data]
        assert "searchable_user" in usernames

    @pytest.mark.asyncio
    async def test_search_excludes_self(self, client: AsyncClient):
        """Search does not return the searching user."""
        token, _ = await register_and_get_token(client, "selfexclude")
        response = await client.get(
            "/api/users/search?q=selfexclude",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        usernames = [u["username"] for u in data]
        assert "selfexclude" not in usernames

    @pytest.mark.asyncio
    async def test_search_short_query(self, client: AsyncClient):
        """Search with query < 2 chars returns 422."""
        token, _ = await register_and_get_token(client, "shortquery")
        response = await client.get(
            "/api/users/search?q=a",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestUserStats:
    """Test user statistics endpoints."""

    @pytest.mark.asyncio
    async def test_get_my_stats(self, client: AsyncClient):
        """Get own stats returns defaults for new user."""
        token, _ = await register_and_get_token(client, "stats1")
        response = await client.get(
            "/api/users/me/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["games_played"] == 0
        assert data["games_won"] == 0
        assert data["win_rate"] == 0.0
        assert data["accuracy_rate"] == 0.0
