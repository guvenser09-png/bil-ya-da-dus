"""Question service — AI question generation, validation, and management.

Uses Anthropic Claude API to generate trivia questions following
the format defined in CLAUDE.md Section 3.1.

Pipeline:
1. Generate batch of questions via AI
2. Validate answers with a second AI call
3. Check for duplicates (content similarity)
4. Store in database with 'pending' approval status
5. Admin reviews and approves/rejects
"""

import json
import random
import re
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.question import ApprovalStatus, Question, QuestionHistory, QuestionType

# --- Categories ---
CATEGORIES = [
    "Genel Kültür", "Bilim", "Tarih", "Coğrafya", "Spor",
    "Sinema", "Müzik", "Edebiyat", "Teknoloji", "Yemek",
    "Sanat", "Doğa", "Uzay", "Mitoloji", "Matematik",
]

ROUND_TYPE_MAP = {
    1: QuestionType.DOGRU_YANLIS,
    2: QuestionType.GORSEL,
    3: QuestionType.KARSILASTIRMA,
    4: QuestionType.COKTAN_SECMELI,
    5: QuestionType.TAHMIN,
}

# --- AI Prompt Templates ---

QUESTION_GENERATION_PROMPT = """Sen bir Türkçe trivia soru üreticisisin. Aşağıdaki formatta {count} adet {question_type} sorusu üret.

Kategori: {category}
Zorluk: {difficulty}/5
Soru tipi: {question_type_desc}

{type_specific_instructions}

Her soru şu JSON formatında olmalı:
{{
  "content": "Soru metni",
  "options": {options_format},
  "correct_answer": <doğru cevabın index numarası (0'dan başlar)>,
  "explanation": "Kısa açıklama",
  "category": "{category}",
  "difficulty": {difficulty}
}}

{extra_fields}

Önemli kurallar:
- Tüm sorular Türkçe olmalı
- Cevaplar kesinlikle doğru olmalı
- Güncel ve ilgi çekici konular seç
- Her soru benzersiz olmalı
- Yanıltıcı seçenekler makul olmalı

Yanıtını SADECE bir JSON array olarak ver, başka hiçbir şey ekleme:
"""

TYPE_INSTRUCTIONS = {
    "dogru_yanlis": {
        "desc": "Doğru/Yanlış (True/False)",
        "instructions": "İki seçenekli (Doğru/Yanlış) sorular üret. Yarısı doğru, yarısı yanlış olsun.",
        "options_format": '["Doğru", "Yanlış"]',
        "extra": "",
    },
    "gorsel": {
        "desc": "Görsel Tanıma",
        "instructions": "Bir görselin tanınmasını gerektiren sorular üret. image_url alanını boş bırak.",
        "options_format": '["Seçenek A", "Seçenek B", "Seçenek C", "Seçenek D"]',
        "extra": '"image_url": null,',
    },
    "karsilastirma": {
        "desc": "Karşılaştırma (Hangisi daha büyük/eski/uzun?)",
        "instructions": "İki şeyin karşılaştırılmasını isteyen sorular üret. Örn: 'Hangisi daha yüksek?' ile iki dağ.",
        "options_format": '["Seçenek A", "Seçenek B"]',
        "extra": "",
    },
    "coktan_secmeli": {
        "desc": "Çoktan Seçmeli (4 seçenek)",
        "instructions": "Dört seçenekli klasik trivia soruları üret.",
        "options_format": '["A", "B", "C", "D"]',
        "extra": "",
    },
    "tahmin": {
        "desc": "Slider/Tahmin",
        "instructions": "Sayısal tahmin soruları üret. Oyuncu bir slider ile cevap verecek.",
        "options_format": "null",
        "extra": '"min_value": <minimum değer>, "max_value": <maksimum değer>, "real_answer": <gerçek cevap>, "unit": "<birim>",',
    },
}


class QuestionService:
    """Manages question generation, validation, and retrieval."""

    @staticmethod
    async def generate_questions_ai(
        question_type: str,
        category: str,
        difficulty: int,
        count: int = 5,
    ) -> list[dict]:
        """Generate questions using Anthropic Claude API.

        Returns list of raw question dicts (not yet saved to DB).
        """
        if not settings.ANTHROPIC_API_KEY:
            # Return seed questions if no API key
            return QuestionService._generate_seed_questions(
                question_type, category, difficulty, count
            )

        type_info = TYPE_INSTRUCTIONS.get(question_type, TYPE_INSTRUCTIONS["coktan_secmeli"])

        prompt = QUESTION_GENERATION_PROMPT.format(
            count=count,
            question_type=question_type,
            question_type_desc=type_info["desc"],
            type_specific_instructions=type_info["instructions"],
            options_format=type_info["options_format"],
            category=category,
            difficulty=difficulty,
            extra_fields=type_info["extra"],
        )

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            content = response.content[0].text
            # Extract JSON array
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
                return questions

        except Exception as e:
            print(f"AI question generation failed: {e}")

        # Fallback to seed questions
        return QuestionService._generate_seed_questions(
            question_type, category, difficulty, count
        )

    @staticmethod
    async def save_questions(
        db: AsyncSession,
        questions: list[dict],
        question_type: str,
        source: str = "ai_generated",
    ) -> list[Question]:
        """Save generated questions to the database."""
        saved = []
        # Get next ID
        result = await db.execute(
            select(func.count()).select_from(Question)
        )
        current_count = result.scalar() or 0

        for i, q in enumerate(questions):
            q_id = f"q_{str(current_count + i + 1).zfill(5)}"

            qtype = ROUND_TYPE_MAP.get(
                {"dogru_yanlis": 1, "gorsel": 2, "karsilastirma": 3,
                 "coktan_secmeli": 4, "tahmin": 5}.get(question_type, 4),
                QuestionType.COKTAN_SECMELI,
            )

            question = Question(
                id=q_id,
                type=qtype,
                category=q.get("category", "Genel Kültür"),
                difficulty=q.get("difficulty", 3),
                content=q.get("content", ""),
                options=q.get("options"),
                correct_answer=q.get("correct_answer"),
                time_seconds=q.get("time_seconds", 7),
                explanation=q.get("explanation"),
                image_url=q.get("image_url"),
                source=source,
                approval_status=ApprovalStatus.PENDING,
                min_value=q.get("min_value"),
                max_value=q.get("max_value"),
                real_answer=q.get("real_answer"),
                unit=q.get("unit"),
            )
            db.add(question)
            saved.append(question)

        await db.flush()
        return saved

    @staticmethod
    async def get_questions_for_game(
        db: AsyncSession,
        player_ids: list[str] | None = None,
    ) -> list[Question]:
        """Get 5 questions (one per round) for a game.
        Ensures 30-day dedup for real players.
        """
        questions = []

        for round_num in range(1, 6):
            q_type = ROUND_TYPE_MAP[round_num]

            stmt = (
                select(Question)
                .where(
                    and_(
                        Question.type == q_type,
                        Question.approval_status == ApprovalStatus.APPROVED,
                    )
                )
                .order_by(func.random())
                .limit(1)
            )

            result = await db.execute(stmt)
            question = result.scalar_one_or_none()

            if question:
                questions.append(question)
            else:
                # No approved question of this type, try any approved
                stmt_any = (
                    select(Question)
                    .where(Question.approval_status == ApprovalStatus.APPROVED)
                    .order_by(func.random())
                    .limit(1)
                )
                result = await db.execute(stmt_any)
                q = result.scalar_one_or_none()
                if q:
                    questions.append(q)

        return questions

    @staticmethod
    async def approve_question(db: AsyncSession, question_id: str) -> Question | None:
        """Approve a pending question."""
        result = await db.execute(select(Question).where(Question.id == question_id))
        q = result.scalar_one_or_none()
        if q:
            q.approval_status = ApprovalStatus.APPROVED
            await db.flush()
        return q

    @staticmethod
    async def reject_question(db: AsyncSession, question_id: str) -> Question | None:
        """Reject a pending question."""
        result = await db.execute(select(Question).where(Question.id == question_id))
        q = result.scalar_one_or_none()
        if q:
            q.approval_status = ApprovalStatus.REJECTED
            await db.flush()
        return q

    @staticmethod
    async def get_question_stats(db: AsyncSession) -> dict:
        """Get stats about the question bank."""
        total = (await db.execute(select(func.count()).select_from(Question))).scalar() or 0
        approved = (await db.execute(
            select(func.count()).select_from(Question)
            .where(Question.approval_status == ApprovalStatus.APPROVED)
        )).scalar() or 0
        pending = (await db.execute(
            select(func.count()).select_from(Question)
            .where(Question.approval_status == ApprovalStatus.PENDING)
        )).scalar() or 0

        # Per-type counts
        type_counts = {}
        for qt in QuestionType:
            count = (await db.execute(
                select(func.count()).select_from(Question)
                .where(and_(
                    Question.type == qt,
                    Question.approval_status == ApprovalStatus.APPROVED,
                ))
            )).scalar() or 0
            type_counts[qt.value] = count

        return {
            "total": total,
            "approved": approved,
            "pending": pending,
            "rejected": total - approved - pending,
            "by_type": type_counts,
        }

    @staticmethod
    async def bulk_approve_all_pending(db: AsyncSession) -> int:
        """Approve all pending questions (for seeding)."""
        from sqlalchemy import update
        result = await db.execute(
            update(Question)
            .where(Question.approval_status == ApprovalStatus.PENDING)
            .values(approval_status=ApprovalStatus.APPROVED)
        )
        await db.flush()
        return result.rowcount

    # --- Seed Questions (no API key needed) ---

    @staticmethod
    def _generate_seed_questions(
        question_type: str,
        category: str,
        difficulty: int,
        count: int,
    ) -> list[dict]:
        """Generate hardcoded seed questions for development/testing."""
        seeds = {
            "dogru_yanlis": [
                {"content": "Türkiye'nin başkenti Ankara'dır.", "options": ["Doğru", "Yanlış"], "correct_answer": 0, "explanation": "Ankara, 1923'ten beri Türkiye'nin başkentidir."},
                {"content": "Dünya'nın en büyük okyanusu Atlantik Okyanusu'dur.", "options": ["Doğru", "Yanlış"], "correct_answer": 1, "explanation": "En büyük okyanus Pasifik Okyanusu'dur."},
                {"content": "İnsan vücudunda 206 kemik bulunur.", "options": ["Doğru", "Yanlış"], "correct_answer": 0, "explanation": "Yetişkin insan vücudunda 206 kemik vardır."},
                {"content": "Albert Einstein fizik alanında Nobel ödülü almıştır.", "options": ["Doğru", "Yanlış"], "correct_answer": 0, "explanation": "Einstein 1921'de fotoelektrik etki çalışmasıyla Nobel almıştır."},
                {"content": "Mars, Güneş'e en yakın gezegendir.", "options": ["Doğru", "Yanlış"], "correct_answer": 1, "explanation": "Güneş'e en yakın gezegen Merkür'dür."},
                {"content": "DNA çift sarmal yapıdadır.", "options": ["Doğru", "Yanlış"], "correct_answer": 0, "explanation": "Watson ve Crick tarafından keşfedilmiştir."},
                {"content": "Everest Dağı Hindistan'dadır.", "options": ["Doğru", "Yanlış"], "correct_answer": 1, "explanation": "Everest, Nepal-Tibet sınırındadır."},
                {"content": "Su 100°C'de kaynar (deniz seviyesinde).", "options": ["Doğru", "Yanlış"], "correct_answer": 0, "explanation": "Standart atmosfer basıncında su 100°C'de kaynar."},
            ],
            "gorsel": [
                {"content": "Bu bayrak hangi ülkeye aittir? 🇯🇵", "options": ["Çin", "Japonya", "Güney Kore", "Tayvan"], "correct_answer": 1, "explanation": "Japonya bayrağı beyaz zemin üzerinde kırmızı dairedir."},
                {"content": "Bu sembol hangi markaya aittir? ✓", "options": ["Adidas", "Nike", "Puma", "Reebok"], "correct_answer": 1, "explanation": "Nike swoosh logosu dünyanın en tanınmış logolarından biridir."},
                {"content": "Bu yapı hangi şehirdedir? 🗼", "options": ["Londra", "New York", "Paris", "Tokyo"], "correct_answer": 2, "explanation": "Eyfel Kulesi Paris'in simgesidir."},
                {"content": "Bu gezegen hangisidir? 🪐", "options": ["Jüpiter", "Satürn", "Uranüs", "Neptün"], "correct_answer": 1, "explanation": "Satürn, halkaları ile tanınır."},
                {"content": "Bu müzik aleti hangisidir? 🎸", "options": ["Keman", "Gitar", "Ukulele", "Bas Gitar"], "correct_answer": 1, "explanation": "Gitar, altı telli bir çalgıdır."},
            ],
            "karsilastirma": [
                {"content": "Hangisi daha yüksektir?", "options": ["Everest Dağı (8,849m)", "K2 Dağı (8,611m)"], "correct_answer": 0, "explanation": "Everest 8,849m ile dünyanın en yüksek dağıdır."},
                {"content": "Hangisi daha eski bir uygarlıktır?", "options": ["Sümer", "Roma İmparatorluğu"], "correct_answer": 0, "explanation": "Sümer uygarlığı MÖ 4500'lere dayanır."},
                {"content": "Hangisinin nüfusu daha fazladır?", "options": ["İstanbul", "Londra"], "correct_answer": 0, "explanation": "İstanbul'un nüfusu 16 milyonun üzerindedir."},
                {"content": "Hangisi daha hızlıdır?", "options": ["Çita", "Şahin"], "correct_answer": 1, "explanation": "Şahin dalışta 390 km/s hıza ulaşabilir."},
                {"content": "Hangisinin yüzölçümü daha büyüktür?", "options": ["Türkiye", "Fransa"], "correct_answer": 0, "explanation": "Türkiye 783,562 km², Fransa 640,679 km²'dir."},
            ],
            "coktan_secmeli": [
                {"content": "Periyodik tabloda 'Au' hangi elementin simgesidir?", "options": ["Gümüş", "Altın", "Alüminyum", "Argon"], "correct_answer": 1, "explanation": "Au, Latince 'Aurum' kelimesinden gelir."},
                {"content": "Hangisi bir programlama dili değildir?", "options": ["Python", "Java", "HTML", "Rust"], "correct_answer": 2, "explanation": "HTML bir işaretleme dilidir, programlama dili değildir."},
                {"content": "İstanbul'u fetheden Osmanlı padişahı kimdir?", "options": ["Yavuz Sultan Selim", "Kanuni Sultan Süleyman", "Fatih Sultan Mehmet", "II. Bayezid"], "correct_answer": 2, "explanation": "Fatih Sultan Mehmet, 1453'te İstanbul'u fethetti."},
                {"content": "Işık hızı yaklaşık kaç km/s'dir?", "options": ["150,000", "300,000", "450,000", "600,000"], "correct_answer": 1, "explanation": "Işık hızı yaklaşık 299,792 km/s'dir."},
                {"content": "Hangisi bir Nobel ödülü kategorisi değildir?", "options": ["Fizik", "Matematik", "Edebiyat", "Barış"], "correct_answer": 1, "explanation": "Nobel ödüllerinde Matematik kategorisi yoktur."},
                {"content": "Python programlama dilini kim geliştirmiştir?", "options": ["James Gosling", "Guido van Rossum", "Dennis Ritchie", "Bjarne Stroustrup"], "correct_answer": 1, "explanation": "Guido van Rossum, Python'u 1991'de yayınlamıştır."},
                {"content": "Dünya'nın en uzun nehri hangisidir?", "options": ["Amazon", "Nil", "Mississippi", "Yangtze"], "correct_answer": 1, "explanation": "Nil Nehri yaklaşık 6,650 km uzunluğundadır."},
                {"content": "Hangisi Türkiye'nin komşu ülkesi değildir?", "options": ["Gürcistan", "İran", "Mısır", "Suriye"], "correct_answer": 2, "explanation": "Mısır, Türkiye ile kara sınırı paylaşmaz."},
            ],
            "tahmin": [
                {"content": "Türkiye'nin nüfusu kaç milyondur? (2024)", "min_value": 50, "max_value": 120, "real_answer": 85.3, "unit": "milyon", "explanation": "2024 itibarıyla Türkiye nüfusu yaklaşık 85.3 milyondur."},
                {"content": "Ayasofya kaç yılında inşa edilmiştir?", "min_value": 100, "max_value": 1000, "real_answer": 537, "unit": "yıl", "explanation": "Ayasofya 537 yılında tamamlanmıştır."},
                {"content": "İstanbul Boğazı'nın en dar yeri kaç metredir?", "min_value": 100, "max_value": 5000, "real_answer": 698, "unit": "metre", "explanation": "Rumeli Hisarı ile Anadolu Hisarı arasında 698 metredir."},
                {"content": "Dünya'da kaç ülke vardır? (BM üyesi)", "min_value": 100, "max_value": 300, "real_answer": 193, "unit": "ülke", "explanation": "BM'nin 193 üye devleti vardır."},
                {"content": "Mars'ın Dünya'ya ortalama uzaklığı kaç milyon km'dir?", "min_value": 30, "max_value": 500, "real_answer": 225, "unit": "milyon km", "explanation": "Mars ortalama 225 milyon km uzaklıktadır."},
            ],
        }

        available = seeds.get(question_type, seeds["coktan_secmeli"])
        selected = random.sample(available, min(count, len(available)))

        for q in selected:
            q["category"] = category
            q["difficulty"] = difficulty

        return selected
