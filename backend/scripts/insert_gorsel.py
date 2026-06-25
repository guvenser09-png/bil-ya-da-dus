"""Görsel (bayrak) sorularını image_url'e göre tekilleştirerek ekler.

Neden ayrı script: tüm bayrak sorularının içeriği aynı ("Bu hangi ülkenin
bayrağıdır?"). seed_questions.py (tip+içerik) hash'iyle tekilleştirdiği için
bayrakların hepsi tek soruya çöküyor. Burada her bayrak image_url ile benzersiz
kabul edilir; aynı bayrak DB'de yoksa eklenir. Tekrar çalıştırılabilir.

Çalıştırma: uv run python scripts/insert_gorsel.py --file scripts/questions_generated.json
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models.question import ApprovalStatus, Question, QuestionType


def gorsel_id(image_url: str) -> str:
    digest = hashlib.sha1(f"gorsel|{image_url.strip().lower()}".encode()).hexdigest()
    return f"q_{digest[:14]}"


async def run(path: Path) -> None:
    data = json.load(path.open(encoding="utf-8"))
    gorsel = [q for q in data if q.get("type") == "gorsel" and q.get("image_url")]
    print(f"Dosyada {len(gorsel)} bayrak sorusu var")

    async with async_session_factory() as db:
        # DB'deki mevcut bayrakların image_url'leri (tekilleştirme anahtarı)
        existing_urls = set(
            (
                await db.execute(
                    select(Question.image_url).where(Question.type == QuestionType.GORSEL)
                )
            ).scalars().all()
        )
        existing_ids = set(
            (await db.execute(select(Question.id))).scalars().all()
        )

        to_add = []
        seen = set()
        skipped = 0
        for q in gorsel:
            url = q["image_url"].strip()
            qid = gorsel_id(url)
            if url in existing_urls or qid in existing_ids or qid in seen:
                skipped += 1
                continue
            seen.add(qid)
            to_add.append(
                Question(
                    id=qid,
                    type=QuestionType.GORSEL,
                    category=q.get("category", "Coğrafya"),
                    difficulty=int(q.get("difficulty", 2)),
                    content=q["content"],
                    options=q.get("options"),
                    correct_answer=q.get("correct_answer"),
                    time_seconds=int(q.get("time_seconds", 7)),
                    explanation=q.get("explanation"),
                    image_url=url,
                    source="ai_generated",
                    approval_status=ApprovalStatus.APPROVED,
                )
            )

        print(f"  zaten var: {skipped}")
        print(f"  eklenecek: {len(to_add)}")
        if to_add:
            db.add_all(to_add)
            await db.commit()
            print(f"✓ {len(to_add)} yeni bayrak sorusu eklendi (approved)")

        total_gorsel = (
            await db.execute(
                select(func.count()).select_from(Question).where(
                    Question.type == QuestionType.GORSEL,
                    Question.approval_status == ApprovalStatus.APPROVED,
                )
            )
        ).scalar()
        total_all = (
            await db.execute(select(func.count()).select_from(Question))
        ).scalar()
        print(f"  Onaylı görsel toplam: {total_gorsel}")
        print(f"  TÜM sorular toplam:  {total_all}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=Path(__file__).parent / "questions_generated.json")
    args = ap.parse_args()
    asyncio.run(run(args.file))
