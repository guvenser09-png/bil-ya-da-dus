"""Tests for question and game API endpoints."""

import pytest
from httpx import AsyncClient


async def register_and_get_token(client: AsyncClient, username: str) -> str:
    """Helper: register a user and return token."""
    response = await client.post("/api/auth/register", json={
        "username": username,
        "password": "test123abc",
        "email": f"{username}@example.com",
    })
    return response.json()["access_token"]


class TestQuestionEndpoints:
    """Test question management API."""

    @pytest.mark.asyncio
    async def test_seed_questions(self, client: AsyncClient):
        """Seed endpoint creates questions."""
        token = await register_and_get_token(client, "qseed1")
        response = await client.post(
            "/api/questions/seed",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_generated"] > 0
        assert data["total_approved"] > 0

    @pytest.mark.asyncio
    async def test_get_question_stats(self, client: AsyncClient):
        """Stats endpoint returns valid data."""
        token = await register_and_get_token(client, "qstats1")
        # Seed first
        await client.post(
            "/api/questions/seed",
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.get(
            "/api/questions/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert "by_type" in data

    @pytest.mark.asyncio
    async def test_generate_questions(self, client: AsyncClient):
        """Generate endpoint creates pending questions."""
        token = await register_and_get_token(client, "qgen1")
        response = await client.post(
            "/api/questions/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "question_type": "coktan_secmeli",
                "category": "Genel Kültür",
                "difficulty": 3,
                "count": 3,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) >= 1
        assert data[0]["approval_status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_categories(self, client: AsyncClient):
        """Categories endpoint returns list."""
        response = await client.get("/api/questions/categories")
        assert response.status_code == 200
        data = response.json()
        assert "Genel Kültür" in data["categories"]


class TestGameEndpoints:
    """Test game API."""

    @pytest.mark.asyncio
    async def test_game_history_empty(self, client: AsyncClient):
        """New user has no game history."""
        token = await register_and_get_token(client, "ghist1")
        response = await client.get(
            "/api/games/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["history"] == []

    @pytest.mark.asyncio
    async def test_active_games(self, client: AsyncClient):
        """Active games endpoint returns list."""
        token = await register_and_get_token(client, "gactive1")
        response = await client.get(
            "/api/games/active",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "active_games" in data

    @pytest.mark.asyncio
    async def test_leaderboard(self, client: AsyncClient):
        """Leaderboard endpoint returns empty for new DB."""
        token = await register_and_get_token(client, "glead1")
        response = await client.get("/api/games/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert "leaderboard" in data


class TestLeaderboardEndpoints:
    """Test Redis-based leaderboard API."""

    @pytest.mark.asyncio
    async def test_daily_leaderboard(self, client: AsyncClient):
        """Daily leaderboard returns data."""
        response = await client.get("/api/leaderboard/daily")
        assert response.status_code == 200
        data = response.json()
        # Günlük Redis seti boşken all-time'a düşülür ("daily_fallback_all_time").
        assert data["period"].startswith("daily")

    @pytest.mark.asyncio
    async def test_weekly_leaderboard(self, client: AsyncClient):
        """Weekly leaderboard returns data."""
        response = await client.get("/api/leaderboard/weekly")
        assert response.status_code == 200
        data = response.json()
        # Haftalık Redis seti boşken all-time'a düşülür ("weekly_fallback_all_time").
        assert data["period"].startswith("weekly")
