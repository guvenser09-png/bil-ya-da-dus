from prometheus_client import Counter, Histogram, Gauge

# Game lifecycle counters
games_started = Counter(
    "quizroyale_games_started_total",
    "Total games started",
)

games_finished = Counter(
    "quizroyale_games_finished_total",
    "Total games finished",
    ["outcome"],  # 'won', 'cancelled', 'completed'
)

# WebSocket connections
active_websockets = Gauge(
    "quizroyale_active_websockets",
    "Active WebSocket connections",
)

# Lobby composition
lobby_real_player_ratio = Histogram(
    "quizroyale_lobby_real_player_ratio",
    "Ratio of real players in a lobby at game start",
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0],
)

# Answer timing
answer_time = Histogram(
    "quizroyale_answer_time_seconds",
    "Time taken by a player to answer (seconds)",
    buckets=[0.5, 1, 2, 3, 5, 7, 8],
)

# Anti-cheat
anti_cheat_flags = Counter(
    "quizroyale_anti_cheat_flags_total",
    "Number of suspicious behaviour flags raised",
    ["reason"],  # 'answer_too_fast', 'slider_exact', 'score_anomaly'
)

# Lobby fill
lobby_fill_failures = Counter(
    "quizroyale_lobby_fill_failures_total",
    "Lobbies cancelled due to insufficient real players",
)

lobby_bot_fills = Counter(
    "quizroyale_lobby_bot_fills_total",
    "Lobbies filled with bots",
)

# Question stats
questions_served = Counter(
    "quizroyale_questions_served_total",
    "Total questions served to players",
    ["round", "type"],
)

correct_answers = Counter(
    "quizroyale_correct_answers_total",
    "Total correct answers given",
    ["round"],
)

# Leaderboard
leaderboard_updates = Counter(
    "quizroyale_leaderboard_updates_total",
    "Total leaderboard score update operations",
    ["board"],  # 'daily', 'weekly', 'seasonal'
)

# Ad events
ad_impressions = Counter(
    "quizroyale_ad_impressions_total",
    "Total ad impressions",
    ["ad_type"],  # 'interstitial', 'rewarded', 'banner'
)

# Session duration
session_duration = Histogram(
    "quizroyale_session_duration_seconds",
    "Duration of a complete game session from lobby join to result screen",
    buckets=[30, 60, 90, 120, 180, 240, 300],
)
