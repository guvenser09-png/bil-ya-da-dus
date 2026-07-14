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

# İstemciden gelen hız bonusunun tavanı (5 soru × 15 sn × 2 puan).
_DAILY_SPEED_BONUS_CAP = 150


class DailyChallengeScoreRequest(BaseModel):
    """Günün 5 Sorusu gönderimi.

    answers: soru sırasıyla cevaplar (şıklı tiplerde index, 'tahmin'de sayı).
    Doğru/yanlış kararını SUNUCU verir (istemci "5/5 yaptım" diyemez); score
    yalnızca HIZ BONUSUDUR, tavanlanır ve sıralamada eşitlik bozmaya yarar.
    """

    score: int = 0
    answers: list | None = None


@router.get("/daily-challenge/status")
async def get_daily_challenge_status(
    user_id: str = Depends(get_current_user_id),
):
    """Ana ekran kartının beslendiği uç — bugün oynandı mı, seri kaç, sonuç ne?

    {played_today, streak, result: {correct_count, results, coins_earned,
    score, rank, total_players, percentile, share_text} | null}
    """
    from app.services import daily_challenge_service as dcs

    played = await dcs.has_played_today(user_id)
    return {
        "played_today": played,
        "streak": await dcs.get_streak(user_id),
        "question_count": 5,
        "max_reward": dcs.DAILY_CHALLENGE_MAX_REWARD,
        "result": await dcs.get_result(user_id) if played else None,
    }


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
    db: AsyncSession = Depends(get_db),
):
    """Günün 5 Sorusu'nu tamamla: değerlendir, COIN ver, sırala, paylaşım kartı üret.

    - Cevaplar SUNUCUDA değerlendirilir → 🟩/🟥 dizisi (paylaşım kartı buradan).
    - Ödül: taban 100 + her doğru 20 → maks 200 altın. Günde BİR kez (Redis SET
      NX ile idempotent); maç ödülünün 500'lük günlük cap'inden AYRI havuz
      (gerekçe: daily_challenge_service modül başlığı).
    - Seri (streak) güncellenir, "Günün 5 Sorusu'nu oyna" görevi işaretlenir.

    Bugün zaten oynandıysa 403 döner (coin tekrar verilmez).
    """
    from app.services import quest_service
    from app.services.daily_challenge_service import (
        build_share_text,
        get_rank_and_total,
        get_today_questions,
        grade_answers,
        percentile_for,
        reward_for_correct_count,
        bump_streak,
        save_result,
        submit_score,
        try_mark_played,
    )
    from app.services.user_service import UserService

    # ATOMİK hak rezervasyonu — çift gönderim ikinci kez ödül ALAMAZ.
    if not await try_mark_played(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bugünkü günlük meydan okumayı zaten oynadınız.",
        )

    questions = await get_today_questions()
    results = grade_answers(questions, body.answers or [])
    correct_count = sum(1 for ok in results if ok)

    # Skor SUNUCUDA belirlenir: sıralamayı DOĞRU SAYISI yönetir (soru başına 100),
    # istemciden gelen hız bonusu yalnızca eşitlik bozar ve TAVANLIDIR (maks 150 =
    # 5 soru × 15 sn × 2). Böylece istemci "score: 999999" gönderip günlük
    # sıralamanın tepesine oturamaz.
    speed_bonus = min(max(0, int(body.score)), _DAILY_SPEED_BONUS_CAP)
    score = correct_count * 100 + speed_bonus
    rank = await submit_score(user_id, score)
    _, total_players = await get_rank_and_total(user_id)

    coins_earned = reward_for_correct_count(correct_count)
    coins_total = 0
    try:
        user = await UserService.get_user_by_id(db, user_id)
        if user:
            user.coins = (user.coins or 0) + coins_earned
            await db.flush()
            await db.refresh(user)
            coins_total = user.coins
    except Exception:  # coin verilemezse bile sonuç ekranı çalışsın
        coins_earned = 0

    streak = await bump_streak(user_id)
    await quest_service.record_daily_challenge(user_id)

    result = {
        "score": score,
        "correct_count": correct_count,
        "question_count": len(results),
        "results": results,
        "coins_earned": coins_earned,
        "coins": coins_total,
        "rank": rank,
        "total_players": total_players,
        "percentile": percentile_for(rank, total_players),
        "streak": streak,
        "share_text": build_share_text(results, correct_count),
        "message": "Skor kaydedildi.",
    }
    await save_result(user_id, result)
    return result


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
