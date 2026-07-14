"""Seed the question bank with a curated set of Turkish trivia questions.

This script is IDEMPOTENT: it can be run multiple times without creating
duplicates. Each question gets a deterministic id derived from a SHA-1 hash
of its (type + normalised content), so re-running only inserts questions that
are not already present.

Questions are loaded from ``scripts/questions_tr.json`` (a plain JSON array)
and inserted with ``approval_status = APPROVED`` so that the game engine
(``QuestionService.get_questions_for_game``) can immediately serve them —
no AI / ANTHROPIC_API_KEY is required.

Usage (from the ``backend`` directory)::

    export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
    uv run python scripts/seed_questions.py

Optional flags::

    uv run python scripts/seed_questions.py --dry-run   # show what would happen
    uv run python scripts/seed_questions.py --file path/to/other.json
    uv run python scripts/seed_questions.py --validate-only  # DB'siz yapısal kontrol
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

# Make sure ``import app...`` works no matter where the script is run from.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from app.models.question import (  # noqa: E402
    ApprovalStatus,
    Question,
    QuestionType,
)

DEFAULT_JSON = BACKEND_ROOT / "scripts" / "questions_tr.json"

# Map the JSON "type" string to the QuestionType enum.
TYPE_MAP = {
    "dogru_yanlis": QuestionType.DOGRU_YANLIS,
    "gorsel": QuestionType.GORSEL,
    "karsilastirma": QuestionType.KARSILASTIRMA,
    "coktan_secmeli": QuestionType.COKTAN_SECMELI,
    "tahmin": QuestionType.TAHMIN,
}

# Default per-type answer time (seconds) used when a question omits it.
DEFAULT_TIME_SECONDS = {
    QuestionType.DOGRU_YANLIS: 7,
    QuestionType.GORSEL: 10,
    QuestionType.KARSILASTIRMA: 8,
    QuestionType.COKTAN_SECMELI: 10,
    QuestionType.TAHMIN: 12,
}

SEED_SOURCE = "seed_tr"


def _normalise(text: str) -> str:
    """Lower-case and collapse whitespace for stable hashing."""
    return re.sub(r"\s+", " ", text.strip().lower())


def deterministic_id(q_type: str, content: str, image_url: str | None = None) -> str:
    """Stable, collision-resistant id for idempotency.

    Format: ``q_<10-hex>`` (fits the String(20) primary key column).

    GÖRSEL sorularda ``image_url`` da hash'e girer: bayrak sorularının METNİ
    hep aynıdır ("Bu bayrak hangi ülkeye aittir?") — sadece tip+içerik hash'i
    kullanılsaydı TÜM bayrak soruları AYNI id'ye çöker ve yalnızca biri
    eklenirdi. Görsel olmayan sorularda davranış DEĞİŞMEZ (image_url yok →
    eski hash girdisiyle birebir aynı id üretilir, mevcut kayıtlar korunur).
    """
    key = f"{q_type}|{_normalise(content)}"
    if image_url:
        key += f"|{image_url.strip()}"
    digest = hashlib.sha1(key.encode()).hexdigest()
    return f"q_{digest[:14]}"


def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array of questions.")
    return data


def validate(raw: dict, idx: int) -> None:
    """Lightweight validation so we fail loudly on bad seed data."""
    q_type = raw.get("type")
    if q_type not in TYPE_MAP:
        raise ValueError(f"[#{idx}] unknown type {q_type!r}")
    if not raw.get("content"):
        raise ValueError(f"[#{idx}] missing content")

    if q_type == "tahmin":
        for field in ("min_value", "max_value", "real_answer", "unit"):
            if raw.get(field) is None:
                raise ValueError(f"[#{idx}] tahmin question missing {field!r}")
    else:
        options = raw.get("options")
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError(f"[#{idx}] {q_type} needs an options list")
        ca = raw.get("correct_answer")
        if not isinstance(ca, int) or not (0 <= ca < len(options)):
            raise ValueError(f"[#{idx}] correct_answer out of range")


def build_question(raw: dict) -> Question:
    q_type = TYPE_MAP[raw["type"]]
    q_id = deterministic_id(raw["type"], raw["content"], raw.get("image_url"))
    return Question(
        id=q_id,
        type=q_type,
        category=raw.get("category", "Genel Kültür"),
        difficulty=int(raw.get("difficulty", 3)),
        content=raw["content"],
        options=raw.get("options"),
        correct_answer=raw.get("correct_answer"),
        time_seconds=int(raw.get("time_seconds", DEFAULT_TIME_SECONDS[q_type])),
        explanation=raw.get("explanation"),
        image_url=raw.get("image_url"),
        source=SEED_SOURCE,
        approval_status=ApprovalStatus.APPROVED,
        min_value=raw.get("min_value"),
        max_value=raw.get("max_value"),
        real_answer=raw.get("real_answer"),
        unit=raw.get("unit"),
    )


def validate_only(path: Path) -> None:
    """DB'siz yapısal doğrulama: dosyayı yükle, valide et, dağılımı raporla.

    CI/lokal kontrol için kullanılır — veritabanı bağlantısı GEREKTİRMEZ.
    Dosya-içi mükerrer id'ler (aynı tip+içerik hash'i) de raporlanır.
    """
    questions = load_questions(path)
    print(f"Loaded {len(questions)} questions from {path}")

    for i, raw in enumerate(questions):
        validate(raw, i)

    # Zorluk aralığı kontrolü (1-5 dışına taşan soru seed edilmemeli).
    for i, raw in enumerate(questions):
        diff = int(raw.get("difficulty", 3))
        if not (1 <= diff <= 5):
            raise ValueError(f"[#{i}] difficulty {diff} 1-5 aralığında değil")
        # Tahmin sorularında gerçek cevap slider aralığının içinde olmalı.
        if raw.get("type") == "tahmin":
            lo, hi, real = raw["min_value"], raw["max_value"], raw["real_answer"]
            if not (lo < hi):
                raise ValueError(f"[#{i}] tahmin: min_value < max_value olmalı")
            if not (lo <= real <= hi):
                raise ValueError(
                    f"[#{i}] tahmin: real_answer ({real}) aralık dışında [{lo},{hi}]"
                )

    # Dosya-içi mükerrerler (deterministic id çakışması).
    seen: dict[str, int] = {}
    dupes = 0
    for i, raw in enumerate(questions):
        qid = deterministic_id(raw["type"], raw["content"], raw.get("image_url"))
        if qid in seen:
            print(f"  DUPE: #{i} aynı içerik #{seen[qid]} ile (id={qid})")
            dupes += 1
        else:
            seen[qid] = i

    # Tip × zorluk dağılımı.
    dist: dict[tuple[str, int], int] = {}
    for raw in questions:
        key = (raw["type"], int(raw.get("difficulty", 3)))
        dist[key] = dist.get(key, 0) + 1
    print("\nTip × zorluk dağılımı:")
    for (q_type, diff), count in sorted(dist.items()):
        print(f"  {q_type:<16} d{diff}  {count}")

    print(f"\nOK — {len(questions)} soru yapısal olarak geçerli, "
          f"{dupes} dosya-içi mükerrer.")
    if dupes:
        raise SystemExit(1)


async def seed(path: Path, dry_run: bool = False) -> None:
    questions = load_questions(path)
    print(f"Loaded {len(questions)} questions from {path}")

    # Validate everything up front.
    for i, raw in enumerate(questions):
        validate(raw, i)

    async with async_session_factory() as session:
        # Pull existing seed ids in one query for fast membership checks.
        existing_ids = set(
            (
                await session.execute(select(Question.id))
            ).scalars().all()
        )

        to_add: list[Question] = []
        seen_in_batch: set[str] = set()
        skipped = 0
        intra_dupes = 0

        for raw in questions:
            q = build_question(raw)
            if q.id in existing_ids:
                skipped += 1
                continue
            if q.id in seen_in_batch:
                # Two seed rows hash to the same id -> duplicate content in file.
                intra_dupes += 1
                continue
            seen_in_batch.add(q.id)
            to_add.append(q)

        print(f"  already in DB : {skipped}")
        print(f"  in-file dupes : {intra_dupes}")
        print(f"  to insert     : {len(to_add)}")

        if dry_run:
            print("Dry run — no changes committed.")
            return

        if to_add:
            session.add_all(to_add)
            await session.commit()
            print(f"Inserted {len(to_add)} new questions (approved).")
        else:
            print("Nothing new to insert — DB already up to date.")

        # Report final counts by type (approved only).
        print("\nApproved question counts by type:")
        for qt in QuestionType:
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(Question)
                    .where(
                        Question.type == qt,
                        Question.approval_status == ApprovalStatus.APPROVED,
                    )
                )
            ).scalar() or 0
            print(f"  {qt.value:<16} {count}")

        total = (
            await session.execute(select(func.count()).select_from(Question))
        ).scalar() or 0
        print(f"  {'TOTAL (all)':<16} {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Turkish trivia questions.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_JSON,
        help="Path to questions JSON (default: scripts/questions_tr.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be inserted without writing to the DB.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="DB'siz yapısal doğrulama: yükle + valide et + dağılımı raporla.",
    )
    args = parser.parse_args()

    if args.validate_only:
        validate_only(args.file)
        return

    asyncio.run(seed(args.file, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
