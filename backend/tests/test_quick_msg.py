"""💬 Hazır mesaj (quick_msg) testleri — güvenli sosyallik.

Kurallar (ws/game.py build_quick_msg_payload):
  - Yalnızca QUICK_MESSAGES izin listesindeki id'ler kabul edilir; metin
    SUNUCU listesinden çözülür (istemci metni asla yayınlanmaz).
  - Serbest metin / bilinmeyen id / string olmayan msg_id → reddedilir (None).
  - Kullanıcı başına saniyede 1 mesaj (rate-limit); pencere dolunca tekrar izin.
"""

import pytest

from app.services.game_service import GameEngine
from app.ws.game import (
    QUICK_MESSAGES,
    QUICK_MSG_COOLDOWN_SECONDS,
    _quick_msg_last_sent,
    build_quick_msg_payload,
)


def _mk_engine(game_id: str = "g_qm") -> GameEngine:
    players = [
        {"user_id": "u1", "username": "ayse", "display_name": "Ayşe", "avatar_id": "a"},
        {"user_id": "u2", "username": "veli", "display_name": "Veli", "avatar_id": "a"},
    ]
    bots = [{"bot_name": "bot1", "difficulty": "easy", "avatar_id": "a"}]
    return GameEngine(game_id, players, bots)


@pytest.fixture(autouse=True)
def _clean_rate_limit():
    """Her test rate-limit haritasını temiz devralsın (testler sızdırmasın)."""
    _quick_msg_last_sent.clear()
    yield
    _quick_msg_last_sent.clear()


class TestQuickMsgAllowlist:
    """İzin listesi: sabit id geçer, serbest metin/bilinmeyen id reddedilir."""

    def test_all_allowed_ids_resolve_to_server_text(self):
        """Listedeki HER id kabul edilir ve metin sunucudan çözülür."""
        engine = _mk_engine()
        now = 100.0
        for i, (msg_id, text) in enumerate(QUICK_MESSAGES.items()):
            payload = build_quick_msg_payload(
                engine, "g_qm", "u1", msg_id, now=now + i * 10
            )
            assert payload is not None
            assert payload["type"] == "quick_msg"
            assert payload["game_id"] == "g_qm"
            assert payload["msg_id"] == msg_id
            assert payload["text"] == text  # metin sunucu listesinden
            assert payload["username"] == "ayse"

    def test_free_text_is_rejected(self):
        """Serbest metin (izin listesinde olmayan string) YAYINLANMAZ."""
        engine = _mk_engine()
        assert build_quick_msg_payload(
            engine, "g_qm", "u1", "seninle kapışırız!", now=1.0
        ) is None
        # Reddedilen istek rate-limit sayacını da doldurmaz.
        assert "u1" not in _quick_msg_last_sent

    def test_unknown_or_non_string_id_rejected(self):
        """Bilinmeyen id, boş değer ve string olmayan tipler reddedilir."""
        engine = _mk_engine()
        assert build_quick_msg_payload(engine, "g_qm", "u1", "qm_yok", now=1.0) is None
        assert build_quick_msg_payload(engine, "g_qm", "u1", None, now=1.0) is None
        assert build_quick_msg_payload(engine, "g_qm", "u1", 42, now=1.0) is None
        assert build_quick_msg_payload(
            engine, "g_qm", "u1", {"text": "hax"}, now=1.0
        ) is None

    def test_expected_catalog_matches_spec(self):
        """İzin listesi ürün kararıyla birebir (5 sabit mesaj)."""
        assert QUICK_MESSAGES == {
            "qm_gl": "İyi şanslar! 🍀",
            "qm_wp": "Helal! 👏",
            "qm_gg": "GG 🔥",
            "qm_ah": "Ah be! 😅",
            "qm_wow": "Vay canına! 😱",
        }


class TestQuickMsgRateLimit:
    """Saniyede 1 koruması: erken tekrar reddedilir, pencere dolunca geçer."""

    def test_second_message_within_window_is_dropped(self):
        engine = _mk_engine()
        assert build_quick_msg_payload(engine, "g_qm", "u1", "qm_gl", now=10.0) is not None
        # Aynı saniye içinde ikinci istek → düşer.
        assert build_quick_msg_payload(engine, "g_qm", "u1", "qm_gg", now=10.4) is None

    def test_allowed_again_after_cooldown(self):
        engine = _mk_engine()
        assert build_quick_msg_payload(engine, "g_qm", "u1", "qm_gl", now=10.0) is not None
        payload = build_quick_msg_payload(
            engine, "g_qm", "u1", "qm_gg", now=10.0 + QUICK_MSG_COOLDOWN_SECONDS + 0.1
        )
        assert payload is not None
        assert payload["text"] == "GG 🔥"

    def test_rate_limit_is_per_user(self):
        """Bir kullanıcının cooldown'u diğerini engellemez."""
        engine = _mk_engine()
        assert build_quick_msg_payload(engine, "g_qm", "u1", "qm_gl", now=10.0) is not None
        payload = build_quick_msg_payload(engine, "g_qm", "u2", "qm_wp", now=10.1)
        assert payload is not None
        assert payload["username"] == "veli"
