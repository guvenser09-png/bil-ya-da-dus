"""Görsel (GORSEL) soruları bayrak sorularıyla yeniden seed'ler.

Eski Wikimedia URL'leri hotlink engeli + yanlış thumb yolları nedeniyle
çalışmıyordu. flagcdn.com doğrudan, hotlink-dostu ve güvenilir.

Çalıştırma:
  cd backend && uv run python scripts/reseed_gorsel.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select

from app.database import async_session_factory
from app.models.question import ApprovalStatus, Question, QuestionType

# (iso2, doğru ülke, [3 çeldirici])
FLAGS = [
    ("jp", "Japonya", ["Çin", "Güney Kore", "Vietnam"]),
    ("tr", "Türkiye", ["Tunus", "Azerbaycan", "Fas"]),
    ("fr", "Fransa", ["Hollanda", "Rusya", "İtalya"]),
    ("de", "Almanya", ["Belçika", "Avusturya", "İspanya"]),
    ("it", "İtalya", ["İrlanda", "Macaristan", "Meksika"]),
    ("br", "Brezilya", ["Arjantin", "Portekiz", "Kolombiya"]),
    ("ca", "Kanada", ["ABD", "İngiltere", "Avustralya"]),
    ("gb", "İngiltere", ["ABD", "Avustralya", "Yeni Zelanda"]),
    ("us", "ABD", ["Liberya", "Malezya", "İngiltere"]),
    ("es", "İspanya", ["Portekiz", "İtalya", "Kolombiya"]),
    ("gr", "Yunanistan", ["İsrail", "Uruguay", "Finlandiya"]),
    ("ch", "İsviçre", ["Danimarka", "Norveç", "Avusturya"]),
    ("se", "İsveç", ["Norveç", "Finlandiya", "Danimarka"]),
    ("cn", "Çin", ["Vietnam", "Japonya", "Moğolistan"]),
    ("kr", "Güney Kore", ["Japonya", "Tayvan", "Tayland"]),
    ("nl", "Hollanda", ["Lüksemburg", "Fransa", "Rusya"]),
]


def build():
    rows = []
    for i, (iso2, correct, distractors) in enumerate(FLAGS):
        pos = i % 4  # doğru cevabın yeri dönsün
        options = list(distractors)
        options.insert(pos, correct)
        rows.append(
            Question(
                id=f"gorsel_flag_{iso2}",
                type=QuestionType.GORSEL,
                category="Coğrafya",
                difficulty=1 + (i % 3),
                content="Bu bayrak hangi ülkeye aittir?",
                options=options,
                correct_answer=pos,
                time_seconds=8,
                explanation=f"Bu bayrak {correct} bayrağıdır.",
                image_url=f"https://flagcdn.com/w320/{iso2}.png",
                source="seed_flags",
                approval_status=ApprovalStatus.APPROVED,
            )
        )
    return rows


async def main():
    async with async_session_factory() as db:
        # Eski görsel soruları temizle
        existing = (await db.execute(
            select(Question.id).where(Question.type == QuestionType.GORSEL)
        )).scalars().all()
        await db.execute(delete(Question).where(Question.type == QuestionType.GORSEL))
        rows = build()
        db.add_all(rows)
        await db.commit()
        print(f"Silinen eski görsel soru: {len(existing)}")
        print(f"Eklenen bayrak sorusu: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
