"""Analitik özet raporu — terminale basar (hafif, SDK'sız).

DATABASE_URL ve REDIS_URL ortam değişkenlerinden okur (app.config üzerinden).
Redis erişilemezse DB tabanlı kısım (kullanıcı sayıları + yeni kayıtlar) yine
basılır; DAU/maç/retention kısmı "Redis yok" olarak işaretlenir.

Kullanım (backend dizininden)::

    export DATABASE_URL="postgresql://.../railway"
    export REDIS_URL="redis://.../0"
    uv run python scripts/metrics_report.py
    # ya da: .venv/bin/python scripts/metrics_report.py

Production (Railway) örneği — servis içindeki env ile::

    railway run python backend/scripts/metrics_report.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ``import app...`` her yerden çalışsın.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import async_session_factory  # noqa: E402
from app.services import analytics_service  # noqa: E402


def _fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"%{v}"


async def _main() -> None:
    async with async_session_factory() as db:
        data = await analytics_service.compute_metrics(db)

    u = data["users"]
    n = data["new_users"]

    print("=" * 48)
    print(f"  ANALİTİK ÖZET  ({data['generated_at']})")
    print("=" * 48)
    print("\nKULLANICILAR")
    print(f"  Toplam       : {u['total']}")
    print(f"  Kayıtlı      : {u['registered']}")
    print(f"  Misafir      : {u['guest']}")

    print("\nYENİ KAYIT")
    print(f"  Son 1 gün    : {n['last_1d']}")
    print(f"  Son 7 gün    : {n['last_7d']}")
    print(f"  Son 30 gün   : {n['last_30d']}")

    print("\nRETENTION")
    print(f"  D1           : {_fmt_pct(data['retention']['d1_pct'])}")
    print(f"  D7           : {_fmt_pct(data['retention']['d7_pct'])}")

    print("\nGÜNLÜK (DAU / MAÇ)")
    if not data["redis_available"]:
        print("  Redis erişilemedi — günlük DAU/maç verisi yok.")
    elif not data["daily"]:
        print("  Veri yok.")
    else:
        print(f"  {'Tarih':<12} {'DAU':>6} {'Maç':>6}")
        for row in data["daily"]:
            print(f"  {row['date']:<12} {row['dau']:>6} {row['matches']:>6}")

    print()


if __name__ == "__main__":
    asyncio.run(_main())
