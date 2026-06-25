from celery import Celery
from celery.schedules import crontab

app = Celery(
    "quizroyale",
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/2",
)

app.conf.timezone = "Europe/Istanbul"

app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]

app.conf.beat_schedule = {
    # Daily challenge is set every midnight Istanbul time
    "daily-challenge": {
        "task": "backend.tasks.daily_tasks.set_daily_challenge",
        "schedule": crontab(hour=0, minute=0),
    },
    # Stale lobby cleanup runs every 5 minutes
    "cleanup-lobbies": {
        "task": "backend.tasks.daily_tasks.cleanup_lobbies",
        "schedule": 300.0,
    },
    # Leaderboard snapshot saved before midnight reset
    "leaderboard-snapshot": {
        "task": "backend.tasks.daily_tasks.snapshot_leaderboard",
        "schedule": crontab(hour=23, minute=55),
    },
}
