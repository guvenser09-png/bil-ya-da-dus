"""Game management endpoints — history, active games, leaderboard, daily challenge."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.game import Game, GameParticipant, GameStatus
from app.models.user import User
from app.utils.security import get_current_user_id

router = APIRouter()


# --- Response schemas ---

class GameSummary(BaseModel):
    id: str
    status: str
    player_count: int
    bot_count: int
    current_round: int
    winner_username: str | None = None
    started_at: str
    ended_at: str | None = None

    model_config = {"from_attributes": True}


class GameHistoryItem(BaseModel):
    game_id: str
    score: int
    rounds_survived: int
    is_winner: bool
    played_at: str


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    display_name: str | None
    avatar_id: str
    total_score: int
    games_won: int
    games_played: int
    win_rate: float
    level: int


# --- Endpoints ---

@router.get("/history")
async def get_game_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's game history."""
    import uuid as uuid_mod

    stmt = (
        select(GameParticipant)
        .where(GameParticipant.user_id == uuid_mod.UUID(user_id))
        .order_by(GameParticipant.joined_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    participants = result.scalars().all()

    history = []
    for p in participants:
        game = p.game
        history.append({
            "game_id": str(p.game_id),
            "score": p.score,
            "rounds_survived": p.eliminated_at_round or 5,
            "is_winner": game.winner_id == uuid_mod.UUID(user_id) if game and game.winner_id else False,
            "played_at": p.joined_at.isoformat() if p.joined_at else None,
        })

    return {"history": history, "count": len(history)}


@router.get("/leaderboard")
async def get_leaderboard(
    period: str = Query("all", pattern=r"^(all|weekly|daily)$"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the global leaderboard.

    Sorted by total_score descending.
    Periods: all (all time), weekly, daily.
    """
    stmt = (
        select(User)
        .where(
            and_(
                User.is_banned == False,  # noqa: E712
                User.is_active == True,   # noqa: E712
                User.games_played > 0,
            )
        )
        .order_by(User.total_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    leaderboard = []
    for rank, user in enumerate(users, 1):
        leaderboard.append({
            "rank": rank,
            "username": user.username,
            "display_name": user.display_name,
            "avatar_id": user.avatar_id,
            "total_score": user.total_score,
            "games_won": user.games_won,
            "games_played": user.games_played,
            "win_rate": user.win_rate,
            "level": user.level,
        })

    return {"leaderboard": leaderboard, "total": len(leaderboard), "period": period}


def _result_from_leaderboard(
    leaderboard: list[dict],
    winner: str | None,
    user_id: str,
    total_rounds: int = 0,
) -> dict | None:
    """Sıralı oyuncu listesinden mobil sonuç biçimini üret.

    Liste skora göre DESC sıralı varsayılır. Kullanıcı listede yoksa None döner
    (çağıran 403 üretir). WS game_finished ile AYNI alanlar:
    {top_players:[ilk3 {username, avatar_id, score, rank, is_winner}],
     my_result:{rank, score, xp_gained, correct_answers, is_winner,
                total_rounds, final_round, coins_earned?},
     winner, total_rounds}.

    Not: xp_gained = bu maçta kazanılan skor (WS your_score ile aynı);
    final_round = oyuncunun ulaştığı son tur (rounds_survived).
    """
    top_players = []
    my_result = None
    for i, row in enumerate(leaderboard):
        rank = i + 1
        if rank <= 3:
            top_players.append({
                "username": row.get("display_name") or row.get("username"),
                "avatar_id": row.get("avatar_id", "default_01"),
                "score": int(row.get("score", 0)),
                "rank": rank,
                "is_winner": bool(row.get("is_winner", False)),
            })
        if str(row.get("user_id")) == str(user_id):
            score = int(row.get("score", 0))
            final_round = int(row.get("rounds_survived", 0))
            my_result = {
                "rank": rank,
                "score": score,
                # WS game_finished'in your_score'u ile aynı kazanım; mobil sonuç
                # ekranı reconnect/REST yolunda da XP'yi gösterebilsin diye eklendi.
                "xp_gained": score,
                "correct_answers": int(row.get("correct_answers", 0)),
                "is_winner": bool(row.get("is_winner", False)),
                "total_rounds": int(total_rounds),
                "final_round": final_round,
                "coins_earned": int(row.get("coins_earned", 0)),
            }
    if my_result is None:
        return None
    return {
        "top_players": top_players,
        "my_result": my_result,
        "winner": winner,
        "total_rounds": int(total_rounds),
    }


@router.get("/{game_id}/result")
async def get_game_result(
    game_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Bitmiş bir maçın sonucunu döndür (WS game_finished'i kaçıranlar için).

    Mobil result_provider WS bağlantısı koptuğunda buraya düşer. Sonuç önce
    canlı oyun motorundan (hâlâ açıksa), yoksa maç bitiminde yazılan Redis
    anlık görüntüsünden üretilir. WS game_finished ile AYNI formatta:
    {top_players:[ilk3], my_result, winner}.

    - 404: maç sonucu bulunamadı (hiç oynanmadı / süresi doldu).
    - 403: maç var ama kullanıcı bu maçta oynamadı.
    """
    import json

    from app.services.game_service import active_games

    # 1) Canlı motor hâlâ bellekteyse (oyun yeni bitti, temizlenmedi) ondan üret.
    engine = active_games.get(game_id)
    if engine is not None and engine.status == "finished":
        final = engine.finish_game()
        leaderboard = []
        for row in final.get("leaderboard", []):
            p = engine.players.get(row["username"])
            leaderboard.append({
                "user_id": p.user_id if p else None,
                "username": row.get("username"),
                "display_name": row.get("display_name"),
                "avatar_id": row.get("avatar_id"),
                "score": int(row.get("score", 0)),
                "correct_answers": int(row.get("correct_answers", 0)),
                "rounds_survived": int(row.get("rounds_survived", 0)),
                "is_winner": bool(row.get("is_winner", False)),
            })
        winner = (final.get("winner") or {}).get("username")
        result = _result_from_leaderboard(
            leaderboard, winner, user_id,
            total_rounds=int(final.get("total_rounds", 0)),
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Bu maçta oynamadınız."
            )
        # Maçta oynanan soruların özeti (mobil "soruları & doğru cevapları gör").
        # Kullanıcının cevapları motordaki round_results'tan kişiselleştirilir.
        from app.ws.game import _attach_user_answers, _build_questions_summary

        questions = _build_questions_summary(engine)
        my_username = next(
            (p.username for p in engine.players.values()
             if str(p.user_id) == str(user_id)),
            None,
        )
        result["questions"] = _attach_user_answers(questions, engine, my_username)
        return result

    # 2) Redis anlık görüntüsü (maç bitiminde yazılır, 24 saat saklanır).
    snapshot = None
    try:
        from app.redis_client import get_redis

        redis = await get_redis()
        raw = await redis.get(f"match:result:{game_id}")
        if raw is not None:
            snapshot = json.loads(raw)
    except Exception:
        snapshot = None

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Maç sonucu bulunamadı."
        )

    result = _result_from_leaderboard(
        snapshot.get("leaderboard", []), snapshot.get("winner"), user_id,
        total_rounds=int(snapshot.get("total_rounds", 0)),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Bu maçta oynamadınız."
        )
    # Maçta oynanan soruların özeti (snapshot'tan). Kullanıcı-bazlı cevaplar
    # snapshot'taki answers_by_round + username_to_uid eşlemesinden üretilir;
    # bulunamazsa sadece soru + doğru cevap döner (yine de yeterli).
    questions = snapshot.get("questions", []) or []
    answers_by_round = snapshot.get("answers_by_round", {}) or {}
    username_to_uid = snapshot.get("username_to_uid", {}) or {}
    my_username = next(
        (uname for uname, uid in username_to_uid.items()
         if str(uid) == str(user_id)),
        None,
    )
    enriched_questions = []
    for item in questions:
        new_item = dict(item)
        if my_username:
            rnd_answers = answers_by_round.get(str(item.get("round")), {})
            ans = rnd_answers.get(my_username)
            if ans is not None:
                new_item["your_answer"] = ans.get("answer")
                new_item["correct_bool"] = bool(ans.get("correct_bool", False))
        enriched_questions.append(new_item)
    result["questions"] = enriched_questions
    return result


@router.get("/active")
async def get_active_games(
    user_id: str = Depends(get_current_user_id),
):
    """Get currently active games."""
    from app.services.game_service import active_games

    games = []
    for game_id, engine in active_games.items():
        games.append({
            "game_id": game_id,
            "status": engine.status,
            "current_round": engine.current_round,
            "alive_count": engine.alive_count,
            "total_players": len(engine.players),
        })

    return {"active_games": games, "count": len(games)}


# ---------------------------------------------------------------------------
# Daily Challenge
# ---------------------------------------------------------------------------

class DailyChallengeScoreRequest(BaseModel):
    score: int


@router.get("/daily-challenge")
async def get_daily_challenge(
    user_id: str = Depends(get_current_user_id),
):
    """Return today's 5 daily challenge questions.

    Returns 403 if the player has already played today.
    """
    from app.services.daily_challenge_service import get_today_questions, has_played_today

    if await has_played_today(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bugünkü günlük meydan okumayı zaten oynadınız.",
        )

    questions = await get_today_questions()
    # Strip server-side fields (correct_answer, real_answer) before sending to client
    client_questions = []
    for q in questions:
        cq = {k: v for k, v in q.items() if k not in ("correct_answer", "real_answer")}
        client_questions.append(cq)

    return {
        "questions": client_questions,
        "question_count": len(client_questions),
    }


@router.post("/daily-challenge/score")
async def submit_daily_challenge_score(
    body: DailyChallengeScoreRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Submit the player's score for today's daily challenge.

    Marks the player as having played today and records the score on the
    daily leaderboard. Returns the player's rank.

    Returns 403 if already played today.
    """
    from app.services.daily_challenge_service import (
        has_played_today,
        mark_as_played,
        submit_score,
    )

    if await has_played_today(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bugünkü günlük meydan okumayı zaten oynadınız.",
        )

    await mark_as_played(user_id)
    rank = await submit_score(user_id, body.score)

    return {
        "score": body.score,
        "rank": rank,
        "message": "Skor kaydedildi.",
    }


@router.get("/daily-challenge/leaderboard")
async def get_daily_challenge_leaderboard(
    limit: int = Query(100, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    """Return the leaderboard for today's daily challenge."""
    from app.services.daily_challenge_service import get_daily_leaderboard

    leaderboard = await get_daily_leaderboard(limit=limit)
    return {
        "leaderboard": leaderboard,
        "count": len(leaderboard),
    }
