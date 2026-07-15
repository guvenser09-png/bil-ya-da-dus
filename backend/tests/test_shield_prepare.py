"""Kalkan yeniden tasarımı testleri.

Kapsam:
  1. prepare_shield(source="gold"): 100 altın düşer + shield_ready set; yetersiz
     bakiyede ALTIN DÜŞMEZ, {ok:false, reason:"insufficient"}.
  2. prepare_shield(source="ad"): altın DÜŞMEZ, reklam doğrulaması + shield_ready;
     aynı nonce iki kez → reddedilir.
  3. prepare_shield geçersiz source → ValueError.
  4. GameEngine.apply_shield_setup: yeni oyuncu (games<5) bedava; veteran kredi
     yoksa 0, kredi (shield_ready) varsa 1 + bayrak tüketilir; botlar 1'de kalır.
  5. POST /api/users/me/prepare-shield uç davranışı (200 ok / 200 insufficient).
"""

import uuid

import pytest

from app.models.user import User
from app.services import shield_service
from app.services.game_service import GameEngine
from app.services.shield_service import SHIELD_GOLD_COST


async def _mk_user(db, *, coins=1000, games_played=1) -> User:
    u = User(
        id=uuid.uuid4(),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@t.co",
        password_hash="x",
        display_name="Test",
        avatar_id="default_01",
        coins=coins,
        games_played=games_played,
    )
    db.add(u)
    await db.flush()
    return u


# ---------------------------------------------------------------------------
# 1) prepare_shield — gold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_gold_deducts_and_sets_flag(db_session, mock_redis):
    """source=gold: bakiye yeterse 100 altın düşer + shield_ready set."""
    u = await _mk_user(db_session, coins=300)

    res = await shield_service.prepare_shield(db_session, str(u.id), "gold")

    assert res["ok"] is True
    assert res["source"] == "gold"
    assert res["coins"] == 300 - SHIELD_GOLD_COST
    assert u.coins == 200
    # Bayrak kondu.
    assert await shield_service.has_shield_ready(str(u.id)) is True


@pytest.mark.asyncio
async def test_prepare_gold_insufficient_no_deduction(db_session, mock_redis):
    """source=gold: bakiye < 100 ise ALTIN DÜŞMEZ, ok:false reason:insufficient."""
    u = await _mk_user(db_session, coins=SHIELD_GOLD_COST - 1)

    res = await shield_service.prepare_shield(db_session, str(u.id), "gold")

    assert res["ok"] is False
    assert res["reason"] == "insufficient"
    assert u.coins == SHIELD_GOLD_COST - 1  # dokunulmadı
    assert await shield_service.has_shield_ready(str(u.id)) is False


# ---------------------------------------------------------------------------
# 2) prepare_shield — ad
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_ad_no_gold_sets_flag(db_session, mock_redis):
    """source=ad: altın DÜŞMEZ; reklam doğrulanır + shield_ready set."""
    u = await _mk_user(db_session, coins=50)  # bakiye düşük olsa da reklam bedava

    res = await shield_service.prepare_shield(
        db_session, str(u.id), "ad", nonce="n-1"
    )

    assert res["ok"] is True
    assert res["source"] == "ad"
    assert u.coins == 50  # altın dokunulmadı
    assert await shield_service.has_shield_ready(str(u.id)) is True


@pytest.mark.asyncio
async def test_prepare_ad_same_nonce_rejected(db_session, mock_redis):
    """Aynı nonce ile ikinci kalkan reklamı reddedilir (idempotency)."""
    u = await _mk_user(db_session, coins=50)

    await shield_service.prepare_shield(db_session, str(u.id), "ad", nonce="dup")
    with pytest.raises(ValueError):
        await shield_service.prepare_shield(db_session, str(u.id), "ad", nonce="dup")


@pytest.mark.asyncio
async def test_prepare_invalid_source(db_session, mock_redis):
    u = await _mk_user(db_session, coins=1000)
    with pytest.raises(ValueError):
        await shield_service.prepare_shield(db_session, str(u.id), "banana")


# ---------------------------------------------------------------------------
# 3) apply_shield_setup — maç başı kalkan kurulumu
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_new_player_gets_free_shield(db_session, mock_redis):
    """Yeni oyuncu (games_played<5): otomatik 1 bedava kalkan."""
    u = await _mk_user(db_session, games_played=2)
    players = [{"user_id": str(u.id), "username": "p1", "display_name": "P", "avatar_id": "a"}]
    bots = [{"bot_name": "bot1", "difficulty": "easy", "avatar_id": "a"}]
    engine = GameEngine("g1", players, bots)

    await engine.apply_shield_setup(db=db_session)

    assert engine.players["p1"].shields == 1  # bedava
    assert engine.players["bot1"].shields == 1  # bot dokunulmadı


@pytest.mark.asyncio
async def test_setup_veteran_without_credit_gets_zero(db_session, mock_redis):
    """Veteran (games>=5) + kredi yok → otomatik kalkan GELMEZ (0)."""
    u = await _mk_user(db_session, games_played=10)
    players = [{"user_id": str(u.id), "username": "p1", "display_name": "P", "avatar_id": "a"}]
    bots = [{"bot_name": "bot1", "difficulty": "easy", "avatar_id": "a"}]
    engine = GameEngine("g2", players, bots)

    await engine.apply_shield_setup(db=db_session)

    assert engine.players["p1"].shields == 0
    assert engine.players["bot1"].shields == 1  # bot yine 1


@pytest.mark.asyncio
async def test_setup_veteran_with_credit_gets_one_and_consumes(db_session, mock_redis):
    """Veteran + shield_ready kredisi → 1 kalkan; bayrak TÜKETİLİR (tek kullanım)."""
    u = await _mk_user(db_session, games_played=10)
    await shield_service.set_shield_ready(str(u.id))
    assert await shield_service.has_shield_ready(str(u.id)) is True

    players = [{"user_id": str(u.id), "username": "p1", "display_name": "P", "avatar_id": "a"}]
    engine = GameEngine("g3", players, [])
    await engine.apply_shield_setup(db=db_session)

    assert engine.players["p1"].shields == 1
    # Bayrak tüketildi → tekrar kurulumda kredi yok.
    assert await shield_service.has_shield_ready(str(u.id)) is False

    engine2 = GameEngine("g4", players, [])
    await engine2.apply_shield_setup(db=db_session)
    assert engine2.players["p1"].shields == 0


@pytest.mark.asyncio
async def test_setup_is_idempotent(db_session, mock_redis):
    """apply_shield_setup iki kez çağrılsa da krediyi bir kez tüketir."""
    u = await _mk_user(db_session, games_played=10)
    await shield_service.set_shield_ready(str(u.id))
    players = [{"user_id": str(u.id), "username": "p1", "display_name": "P", "avatar_id": "a"}]
    engine = GameEngine("g5", players, [])

    await engine.apply_shield_setup(db=db_session)
    await engine.apply_shield_setup(db=db_session)  # ikinci çağrı no-op

    assert engine.players["p1"].shields == 1  # ilk kurulumdaki değer korunur


# ---------------------------------------------------------------------------
# 4) Uç: POST /api/users/me/prepare-shield
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_endpoint_prepare_gold(client, mock_redis):
    """Uç: source=gold ile 100 altın düşer, ok:true döner."""
    from tests.test_users import register_and_get_token

    token, _ = await register_and_get_token(client, "shielduser")
    resp = await client.post(
        "/api/users/me/prepare-shield",
        json={"source": "gold"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    # Başlangıç 300 → 200.
    assert data["coins"] == 200


@pytest.mark.asyncio
async def test_endpoint_prepare_gold_insufficient(client, db_session, mock_redis):
    """Uç: bakiye yetmezse 200 + ok:false reason:insufficient (400 DEĞİL)."""
    from app.utils.security import create_access_token

    u = await _mk_user(db_session, coins=50)
    await db_session.commit()
    token = create_access_token(str(u.id))
    resp = await client.post(
        "/api/users/me/prepare-shield",
        json={"source": "gold"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["reason"] == "insufficient"
