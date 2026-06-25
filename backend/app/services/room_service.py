"""Özel oda servisi — arkadaşlarla kod tabanlı, host kontrollü oyun.

Tamamen in-memory (Redis/DB yok). Oda yaşam döngüsü:
1. Bir oyuncu "yeni oda" açar → host olur, 6 haneli okunur bir kod üretilir.
2. Arkadaşlar bu kodu girerek odaya katılır (MAX_PLAYERS sınırına kadar).
3. SADECE host odayı başlatabilir; üyeler oyuncu listesine çevrilir,
   kalan slotlar botlarla doldurulur (matchmaking bot üretimi yeniden kullanılır).
4. Üye çıkınca oda güncellenir; host çıkınca veya oda boşalınca oda kapanır.

Tüm durum tek bir asyncio event loop içinde değiştiğinden (FastAPI/uvicorn)
düz dict erişimi güvenlidir — kilit gerekmez.
"""

from __future__ import annotations

import random
import string
import uuid as uuid_mod
from typing import Any

from app.config import settings
from app.services.matchmaking_service import BOT_AVATARS, _BOT_DIFFICULTIES
from app.services.bot_service import generate_bot_name

# Karıştırılması kolay karakterler (0/O, 1/I/L) hariç tutulur → okunur kod.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 6

# Özel oda maçı en az kaç GERÇEK oyuncu ile başlayabilir. Oda botla
# doldurulmadığından arkadaşlar gerçek oyuncularla (en az 2 kişi) oynar.
MIN_PLAYERS_TO_START = 2


class Room:
    """Tek bir özel odanın in-memory durumu."""

    def __init__(self, code: str, host_user_id: str):
        self.code = code
        self.host_user_id = host_user_id
        # [{user_id, username, display_name, avatar_id}]
        self.members: list[dict[str, Any]] = []
        self.status = "waiting"  # waiting | starting | in_game
        self.game_id: str | None = None

    # ------------------------------------------------------------------
    # Özellikler
    # ------------------------------------------------------------------

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def is_full(self) -> bool:
        return self.member_count >= settings.MAX_PLAYERS

    def has_member(self, user_id: str) -> bool:
        return any(m["user_id"] == user_id for m in self.members)

    # ------------------------------------------------------------------
    # Üyelik
    # ------------------------------------------------------------------

    def add_member(
        self,
        user_id: str,
        username: str,
        display_name: str,
        avatar_id: str,
    ) -> bool:
        """Odaya üye ekler.

        Returns:
            Eklendiyse True; oda doluysa veya üye zaten varsa False.
        """
        if self.is_full:
            return False
        if self.has_member(user_id):
            return False
        self.members.append(
            {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "avatar_id": avatar_id,
            }
        )
        return True

    def remove_member(self, user_id: str) -> bool:
        """Odadan üye çıkarır.

        Returns:
            Üye bulunup çıkarıldıysa True.
        """
        before = len(self.members)
        self.members = [m for m in self.members if m["user_id"] != user_id]
        return len(self.members) < before

    # ------------------------------------------------------------------
    # Oyuna dönüştürme
    # ------------------------------------------------------------------

    def players_for_game(self) -> list[dict[str, Any]]:
        """Üyeleri oyun motorunun beklediği players listesine çevirir."""
        return [
            {
                "user_id": m["user_id"],
                "username": m["username"],
                "display_name": m["display_name"],
                "avatar_id": m["avatar_id"],
            }
            for m in self.members
        ]

    def build_bots(self) -> list[dict[str, Any]]:
        """Kalan slotları MAX_PLAYERS'a kadar botlarla doldurur.

        matchmaking servisindeki bot katalogunu (isim/avatar/zorluk) yeniden
        kullanır. Üye/bot isim çakışmalarını önler.

        Returns:
            [{bot_name, difficulty, avatar_id}] listesi.
        """
        bots: list[dict[str, Any]] = []
        used_names: set[str] = {m.get("username", "") for m in self.members}

        bots_needed = settings.MAX_PLAYERS - self.member_count
        for _ in range(bots_needed):
            name = generate_bot_name()
            attempts = 0
            while name in used_names and attempts < 50:
                name = generate_bot_name()
                attempts += 1
            difficulty = _BOT_DIFFICULTIES[min(len(bots), len(_BOT_DIFFICULTIES) - 1)]
            bots.append(
                {
                    "bot_name": name,
                    "difficulty": difficulty,
                    "avatar_id": random.choice(BOT_AVATARS),
                }
            )
            used_names.add(name)
        return bots

    def member_list_for_client(self) -> list[dict[str, Any]]:
        """İstemciye gönderilecek üye listesi (host işaretiyle)."""
        return [
            {
                "user_id": m["user_id"],
                "username": m["username"],
                "display_name": m["display_name"],
                "avatar_id": m["avatar_id"],
                "is_host": m["user_id"] == self.host_user_id,
            }
            for m in self.members
        ]


class RoomManager:
    """Özel odaların yaşam döngüsünü yönetir (process geneli paylaşılır)."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def _generate_code(self) -> str:
        """Benzersiz, okunur 6 haneli oda kodu üretir."""
        for _ in range(1000):
            code = "".join(random.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if code not in self.rooms:
                return code
        # Çok düşük olasılık: çakışma sürerse UUID tabanlı yedek.
        return uuid_mod.uuid4().hex[:_CODE_LENGTH].upper()

    def create_room(
        self,
        host_user_id: str,
        username: str,
        display_name: str,
        avatar_id: str,
    ) -> Room:
        """Yeni bir oda oluşturur; bağlanan kullanıcı host ve ilk üye olur."""
        code = self._generate_code()
        room = Room(code=code, host_user_id=host_user_id)
        room.add_member(host_user_id, username, display_name, avatar_id)
        self.rooms[code] = room
        return room

    def get_room(self, code: str) -> Room | None:
        """Verilen koddaki odayı döndürür (kod büyük harfe normalize edilir)."""
        if not code:
            return None
        return self.rooms.get(code.upper())

    def add_member(
        self,
        code: str,
        user_id: str,
        username: str,
        display_name: str,
        avatar_id: str,
    ) -> tuple[Room | None, str | None]:
        """Var olan odaya üye ekler.

        Returns:
            (room, error). Başarılıysa (room, None); aksi halde
            (None, "room_not_found" | "room_full" | "already_in_room") veya
            (room, None) idempotent yeniden katılımda.
        """
        room = self.get_room(code)
        if room is None:
            return None, "room_not_found"
        if room.has_member(user_id):
            # Idempotent: aynı kullanıcı yeniden bağlanırsa hata verme.
            return room, None
        if room.is_full:
            return None, "room_full"
        room.add_member(user_id, username, display_name, avatar_id)
        return room, None

    def remove_member(self, code: str, user_id: str) -> tuple[Room | None, bool]:
        """Odadan üye çıkarır; boşalırsa veya host çıkarsa oda kapanır.

        Returns:
            (room, closed). ``closed`` True ise oda artık yönetilmiyor.
            Oda hiç yoksa (None, False).
        """
        room = self.get_room(code)
        if room is None:
            return None, False

        is_host_leaving = user_id == room.host_user_id
        room.remove_member(user_id)

        # Host çıkarsa ya da oda boşalırsa odayı kapat.
        if is_host_leaving or room.member_count == 0:
            self.rooms.pop(room.code, None)
            return room, True
        return room, False

    def remove_room(self, code: str) -> None:
        """Odayı yönetimden kaldırır."""
        if code:
            self.rooms.pop(code.upper(), None)


# Process geneli paylaşılan oda yöneticisi.
room_manager = RoomManager()
