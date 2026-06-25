"""WebSocket özel oda endpoint'i — arkadaşlarla kod tabanlı, host kontrollü oyun.

Bağlantı URL'leri:
    Yeni oda aç:  ws://host/ws/room/new?token=<JWT_ACCESS_TOKEN>
    Odaya katıl:  ws://host/ws/room/{CODE}?token=<JWT_ACCESS_TOKEN>

Akış
----
1. Token doğrulanır (geçersiz → close 4001).
2. code == "new" ise yeni oda oluşturulur (bağlanan = host); gerçek kod
   ``room_created`` ile döner.
3. Aksi halde var olan odaya katılınır. Oda yoksa ``error`` (room_not_found),
   doluysa ``error`` (room_full) + close.
4. SADECE host ``start`` gönderebilir (en az 2 gerçek üye gerekir) → oda
   'in_game' olur, üyeler players listesine çevrilir, BOT EKLENMEZ (arkadaşlar
   gerçek oyuncularla oynar), create_game + run_game tetiklenir ve herkese
   ``room_starting {game_id}`` yayınlanır.
5. Bağlantı kopunca üye çıkarılır; host çıkarsa oda kapanır.

Mesaj protokolü
---------------
Server → Client:
    {"type": "room_created",  "code": "...", "members": [...], "is_host": true}
    {"type": "room_joined",   "code": "...", "members": [...], "is_host": bool,
                              "host_user_id": "..."}
    {"type": "member_joined",  "member": {...}, "members": [...]}
    {"type": "member_left",    "user_id": "...", "members": [...]}
    {"type": "room_starting",  "game_id": "..."}
    {"type": "room_closed",    "reason": "..."}
    {"type": "error",          "message": "..."}

Client → Server:
    {"action": "start"}   # SADECE host
    {"action": "leave"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid as uuid_mod
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.services.game_service import create_game
from app.services.room_service import MIN_PLAYERS_TO_START, Room, room_manager
from app.utils.security import decode_token
from app.ws.game import run_game

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Bağlantı Yöneticisi (lobby.py ConnectionManager desenini izler)
# ---------------------------------------------------------------------------

class RoomConnectionManager:
    """Tüm canlı oda WebSocket bağlantılarının merkezi kaydı.

    Tek bir asyncio event loop içinde çalışır → kilit gerekmez.
    """

    def __init__(self) -> None:
        # user_id → (websocket, room_code)
        self.connections: dict[str, tuple[WebSocket, str]] = {}
        # room_code → o odaya bağlı user_id kümesi
        self.room_members: dict[str, set[str]] = {}

    async def connect(self, user_id: str, websocket: WebSocket, code: str) -> None:
        """user_id'yi *code* odasına kaydeder (yeniden bağlanmada eskisini temizler)."""
        if user_id in self.connections:
            old_code = self.connections[user_id][1]
            self._remove_from_members(user_id, old_code)
        self.connections[user_id] = (websocket, code)
        self.room_members.setdefault(code, set()).add(user_id)

    def disconnect(self, user_id: str) -> str | None:
        """user_id kaydını siler. Bağlı olduğu oda kodunu döndürür (yoksa None)."""
        if user_id not in self.connections:
            return None
        _, code = self.connections.pop(user_id)
        self._remove_from_members(user_id, code)
        return code

    def _remove_from_members(self, user_id: str, code: str) -> None:
        if code in self.room_members:
            self.room_members[code].discard(user_id)
            if not self.room_members[code]:
                del self.room_members[code]

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        """Tek bir bağlı kullanıcıya JSON mesaj gönderir (hataları yutar)."""
        entry = self.connections.get(user_id)
        if entry is None:
            return
        ws, _ = entry
        try:
            await ws.send_text(json.dumps(message, default=str))
        except Exception:
            logger.debug("send_to_user(%s): gönderim başarısız", user_id)

    async def broadcast_to_room(
        self,
        code: str,
        message: dict[str, Any],
        exclude_user_id: str | None = None,
    ) -> None:
        """*code* odasındaki tüm bağlı üyelere JSON mesaj yayınlar."""
        members = self.room_members.get(code)
        if not members:
            return
        payload = json.dumps(message, default=str)
        for uid in list(members):
            if exclude_user_id is not None and uid == exclude_user_id:
                continue
            entry = self.connections.get(uid)
            if entry is None:
                continue
            ws, _ = entry
            try:
                await ws.send_text(payload)
            except Exception:
                logger.debug("broadcast_to_room(%s): %s gönderimi başarısız", code, uid)


# Modül düzeyi singleton
manager = RoomConnectionManager()


# ---------------------------------------------------------------------------
# JWT doğrulama yardımcısı (game.py _authenticate_ws_token ile aynı)
# ---------------------------------------------------------------------------

def _authenticate_ws_token(token: str) -> dict[str, Any] | None:
    """WebSocket query param JWT token'ını çözer. Payload veya None döner."""
    try:
        return decode_token(token, expected_type="access")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Oyun başlatma (host'a özel)
# ---------------------------------------------------------------------------

async def _start_room_game(room: Room) -> None:
    """Odayı oyuna dönüştürür: SADECE gerçek üyelerle (botsuz) başlat.

    Özel oda akışı arkadaşlar arası düello içindir; oda 20'ye bot ile
    DOLDURULMAZ. Maç yalnızca odadaki gerçek üyelerle (en az 2) oynanır.
    Oyun motoru 2 oyuncuyla 5 tur + eleme + kazanan akışını destekler.
    """
    room.status = "in_game"
    room.game_id = str(uuid_mod.uuid4())

    players = room.players_for_game()
    bots: list[dict[str, Any]] = []  # Özel odada bot YOK.

    create_game(game_id=room.game_id, players=players, bots=bots)
    asyncio.create_task(
        run_game(room.game_id, players, bots),
        name=f"room-game-{room.game_id}",
    )

    await manager.broadcast_to_room(room.code, {
        "type": "room_starting",
        "game_id": room.game_id,
    })
    logger.info(
        "Oda %s başlatıldı (botsuz): game_id=%s üye=%d",
        room.code, room.game_id, len(players),
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/room/{code}")
async def room_websocket(websocket: WebSocket, code: str) -> None:
    """Özel oda WebSocket endpoint'i.

    ``code == "new"`` → yeni oda; aksi halde var olan odaya katıl.
    """
    # ------------------------------------------------------------------
    # 1. Token doğrula (accept'ten önce)
    # ------------------------------------------------------------------
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token gerekli.")
        return

    payload = _authenticate_ws_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Geçersiz veya süresi dolmuş token.")
        return

    user_id: str = payload.get("sub", "")
    if not user_id:
        await websocket.close(code=4001, reason="Token içinde kullanıcı bilgisi yok.")
        return

    # İstemci kimlik bilgileri (query param ile gelir; yoksa makul varsayılan)
    qp = websocket.query_params
    username = qp.get("username") or f"player_{user_id[:6]}"
    display_name = qp.get("display_name") or username
    avatar_id = qp.get("avatar_id") or "default_01"

    await websocket.accept()

    # ------------------------------------------------------------------
    # 2. Oda oluştur veya katıl
    # ------------------------------------------------------------------
    is_host = False
    room: Room | None = None

    if code == "new":
        room = room_manager.create_room(user_id, username, display_name, avatar_id)
        is_host = True
        await manager.connect(user_id, websocket, room.code)
        await websocket.send_text(json.dumps({
            "type": "room_created",
            "code": room.code,
            "members": room.member_list_for_client(),
            "is_host": True,
        }, default=str))
        logger.info("Kullanıcı %s yeni oda açtı: %s", user_id, room.code)
    else:
        room, error = room_manager.add_member(
            code, user_id, username, display_name, avatar_id
        )
        if error == "room_not_found" or room is None:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Oda bulunamadı.",
                "code": "room_not_found",
            }))
            await websocket.close(code=4004, reason="Oda bulunamadı.")
            return
        if error == "room_full":
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Oda dolu.",
                "code": "room_full",
            }))
            await websocket.close(code=4003, reason="Oda dolu.")
            return

        is_host = user_id == room.host_user_id
        await manager.connect(user_id, websocket, room.code)
        await websocket.send_text(json.dumps({
            "type": "room_joined",
            "code": room.code,
            "members": room.member_list_for_client(),
            "is_host": is_host,
            "host_user_id": room.host_user_id,
        }, default=str))

        # Diğer üyelere yeni katılanı bildir (katılana gönderme).
        new_member = next(
            (m for m in room.member_list_for_client() if m["user_id"] == user_id),
            None,
        )
        await manager.broadcast_to_room(
            room.code,
            {
                "type": "member_joined",
                "member": new_member,
                "members": room.member_list_for_client(),
            },
            exclude_user_id=user_id,
        )
        logger.info("Kullanıcı %s odaya katıldı: %s", user_id, room.code)

    room_code = room.code

    # ------------------------------------------------------------------
    # 3. Mesaj döngüsü
    # ------------------------------------------------------------------
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Geçersiz JSON formatı.",
                }))
                continue

            action: str = message.get("action", "")

            # ----------------------------------------------------------
            # action: start (SADECE host)
            # ----------------------------------------------------------
            if action == "start":
                current = room_manager.get_room(room_code)
                if current is None:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Oda artık mevcut değil.",
                    }))
                    continue
                if user_id != current.host_user_id:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Yalnızca oda sahibi oyunu başlatabilir.",
                    }))
                    continue
                if current.status != "waiting":
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Oyun zaten başladı veya başlatılıyor.",
                    }))
                    continue
                # Oda botla doldurulmaz → maç yalnızca gerçek üyelerle oynanır.
                # En az 2 gerçek oyuncu yoksa başlatma reddedilir.
                if current.member_count < MIN_PLAYERS_TO_START:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": (
                            f"En az {MIN_PLAYERS_TO_START} oyuncu gerekli. "
                            "Arkadaşın odaya katılmasını bekle."
                        ),
                        "code": "not_enough_players",
                    }))
                    continue
                current.status = "starting"
                await _start_room_game(current)

            # ----------------------------------------------------------
            # action: leave
            # ----------------------------------------------------------
            elif action == "leave":
                left_room, closed = room_manager.remove_member(room_code, user_id)
                manager.disconnect(user_id)
                if left_room is not None:
                    if closed:
                        await manager.broadcast_to_room(room_code, {
                            "type": "room_closed",
                            "reason": "Oda sahibi ayrıldı veya oda boşaldı.",
                        })
                    else:
                        await manager.broadcast_to_room(room_code, {
                            "type": "member_left",
                            "user_id": user_id,
                            "members": left_room.member_list_for_client(),
                        })
                await websocket.send_text(json.dumps({
                    "type": "room_left",
                    "message": "Odadan ayrıldınız.",
                }))
                # Ayrıldıktan sonra bağlantıyı kapat.
                await websocket.close(code=1000, reason="Odadan ayrıldınız.")
                return

            # ----------------------------------------------------------
            # Bilinmeyen action
            # ----------------------------------------------------------
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Bilinmeyen action: '{action}'",
                }))

    except WebSocketDisconnect:
        logger.info("Kullanıcı %s oda WS bağlantısı koptu (%s)", user_id, room_code)
    except Exception:
        logger.exception("room_websocket beklenmeyen hata (user=%s)", user_id)
    finally:
        # ------------------------------------------------------------------
        # Çıkış temizliği: üyeyi çıkar, kalanları bilgilendir.
        # ------------------------------------------------------------------
        manager.disconnect(user_id)
        # Oda hâlâ varsa ve oyuna başlamadıysa üyeyi düşür.
        existing = room_manager.get_room(room_code)
        if existing is not None and existing.status == "waiting":
            left_room, closed = room_manager.remove_member(room_code, user_id)
            if left_room is not None:
                if closed:
                    await manager.broadcast_to_room(room_code, {
                        "type": "room_closed",
                        "reason": "Oda sahibi ayrıldı veya oda boşaldı.",
                    })
                else:
                    await manager.broadcast_to_room(room_code, {
                        "type": "member_left",
                        "user_id": user_id,
                        "members": left_room.member_list_for_client(),
                    })
        logger.debug("Oda temizliği tamamlandı: user=%s code=%s", user_id, room_code)
