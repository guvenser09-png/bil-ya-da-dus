"""User model — player accounts and profiles."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class User(Base):
    """Player account with profile, stats, and currency."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))

    # Auth provider (for future OAuth)
    auth_provider: Mapped[str | None] = mapped_column(
        String(20)  # "email", "google", "apple", None
    )
    auth_provider_id: Mapped[str | None] = mapped_column(String(255))

    # Profile
    display_name: Mapped[str | None] = mapped_column(String(50))
    avatar_id: Mapped[str] = mapped_column(
        String(100), default="robot"
    )
    bio: Mapped[str | None] = mapped_column(String(140))
    interest_tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True  # max 5 tags, e.g. ["sinema", "spor", "müzik"]
    )

    # Progression
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    season_level: Mapped[int] = mapped_column(Integer, default=1)

    # Battle Pass / Sezon (pay-to-win YOK; ödüller altın/kozmetik)
    # season_points: bu sezonda toplanan kümülatif puan.
    # season_tier: season_points'e göre hesaplanan ulaşılmış kademe.
    # has_battle_pass: premium hattı açan (IAP ile alınan) pass sahipliği.
    # season_claimed_free / season_claimed_premium: claim edilmiş tier'ların listesi.
    season_points: Mapped[int] = mapped_column(Integer, default=0)
    season_tier: Mapped[int] = mapped_column(Integer, default=0)
    has_battle_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    season_claimed_free: Mapped[list | None] = mapped_column(JSON, nullable=True)
    season_claimed_premium: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Currency (tek oyun-içi para birimi: altın = coins)
    # Yeni oyuncuya başlangıç altını: ekonomiyi (turnuva girişi + karakter
    # satın alma) hemen oynanabilir kılar. Eski satırlar etkilenmez (migration yok).
    coins: Mapped[int] = mapped_column(Integer, default=1000)
    # Vestigial: artık hiçbir kod okumaz/yazmaz; kolon geriye dönük uyumluluk
    # için tutulur (migration yazılmadı).
    gems: Mapped[int] = mapped_column(Integer, default=0)

    # Günlük ödül + seri (streak)
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_claim_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Gelir modeli anti-farm / kazanç takibi (pay-to-win YOK) ---
    # Maç ödülü günlük cap'i: UTC gün bazlı; gün değişince sıfırlanır.
    # match_reward_date: en son maç ödülü verilen UTC gün (YYYY-MM-DD string).
    # match_reward_coins_today: o gün maçtan kazanılan toplam coin (cap 500).
    match_reward_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    match_reward_coins_today: Mapped[int] = mapped_column(Integer, default=0)

    # Ödüllü reklam günlük limiti: UTC gün bazlı sayaç.
    # ad_reward_date: en son ödüllü reklam izlenen UTC gün (YYYY-MM-DD string).
    # ad_reward_count_today: o gün izlenen ödüllü reklam sayısı (cap 5).
    ad_reward_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ad_reward_count_today: Mapped[int] = mapped_column(Integer, default=0)

    # Starter pack (tek seferlik, ilk 48 saat) satın alındı mı?
    starter_pack_purchased: Mapped[bool] = mapped_column(Boolean, default=False)

    # Kuşanılmış kozmetikler (COIN ile alınır; sahiplik UserCosmetic'te)
    equipped_frame: Mapped[str | None] = mapped_column(String(50), nullable=True)
    equipped_name_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    equipped_effect: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Stats
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    games_won: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    favorite_category: Mapped[str | None] = mapped_column(String(50))
    total_correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    total_questions_answered: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Monetization (iş mantığı Ajan B'de; burada sadece alan tanımı)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    # Hesap silme (KVKK/GDPR soft-delete + anonimleştirme damgası)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    game_participations = relationship(
        "GameParticipant", back_populates="user", lazy="selectin"
    )
    won_games = relationship(
        "Game", back_populates="winner", foreign_keys="Game.winner_id", lazy="selectin"
    )

    @property
    def accuracy_rate(self) -> float:
        """Calculate answer accuracy percentage."""
        if self.total_questions_answered == 0:
            return 0.0
        return round(self.total_correct_answers / self.total_questions_answered * 100, 1)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
