"""Workflow'un urettigi gorsel-soru GERCEKLERINI alir, her dogru konunun
Wikipedia kucuk-resmini ceker, YUKLENEBILIRLIK testinden gecirir ve gorsel
sorusunu kurar. Bozuk/erisilemeyen gorseller ELENIR.

Girdi: workflow ciktisi (validated: [{kind, category, difficulty, correct_label,
        tr_title, en_title, distractors[3], explanation}])
Cikti: scripts/questions_gorsel_rich.json  (insert_gorsel.py ile eklenir)

Calistirma: uv run python scripts/assemble_gorsel_rich.py <workflow_output.json>
"""
import json
import random
import sys
import urllib.parse
import urllib.request

UA = "BilYaDaDus/1.0 (egitim amacli trivia; iletisim: destek@bilyadadus.com)"
CONTENT_BY_KIND = {
    "landmark": "Bu hangi ünlü yapıdır?",
    "artwork": "Bu hangi sanat eseridir?",
    "place": "Burası neresidir?",
}
OK_TYPES = ("image/jpeg", "image/png", "image/webp", "image/jpg")


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def wiki_thumb(lang: str, title: str, size: int = 480) -> str | None:
    q = urllib.parse.urlencode({
        "action": "query", "titles": title, "prop": "pageimages",
        "piprop": "thumbnail", "pithumbsize": size, "format": "json", "redirects": "1",
    })
    url = f"https://{lang}.wikipedia.org/w/api.php?{q}"
    try:
        data = _get_json(url)
    except Exception:
        return None
    pages = (data.get("query", {}) or {}).get("pages", {}) or {}
    for p in pages.values():
        src = (p.get("thumbnail") or {}).get("source")
        if src:
            return src
    return None


def is_loadable(url: str) -> bool:
    """Gorsel gercekten yukleniyor mu: HTTP 200 + image/* (svg haric) + makul boyut."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status != 200:
                return False
            ct = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ct not in OK_TYPES:
                return False
            chunk = r.read(2048)
            return len(chunk) > 500
    except Exception:
        return False


def main(path: str) -> None:
    data = json.load(open(path, encoding="utf-8"))
    items = data.get("result", data).get("validated", [])
    print(f"Girdi: {len(items)} aday gorsel-soru")

    out = []
    seen_urls = set()
    rnd = random.Random(1453)  # deterministik karistirma
    stats = {"ok": 0, "no_image": 0, "dead": 0, "bad_options": 0, "dup": 0}

    for it in items:
        kind = it.get("kind", "landmark")
        correct = (it.get("correct_label") or "").strip()
        distractors = [d.strip() for d in (it.get("distractors") or []) if d and d.strip()]
        # secenekler: dogru + 3 benzersiz celdirici (dogruyla cakismayan)
        distractors = [d for d in dict.fromkeys(distractors) if d != correct][:3]
        if not correct or len(distractors) < 3:
            stats["bad_options"] += 1
            continue

        thumb = None
        for lang, title in (("tr", it.get("tr_title")), ("en", it.get("en_title"))):
            if not title:
                continue
            thumb = wiki_thumb(lang, title)
            if thumb and is_loadable(thumb):
                break
            thumb = None
        if not thumb:
            stats["no_image" if thumb is None else "dead"] += 1
            continue
        if thumb in seen_urls:
            stats["dup"] += 1
            continue
        seen_urls.add(thumb)

        options = [correct] + distractors
        rnd.shuffle(options)
        out.append({
            "type": "gorsel",
            "category": it.get("category", "Genel Kültür"),
            "difficulty": int(it.get("difficulty", 2)),
            "content": CONTENT_BY_KIND.get(kind, "Bu görselde ne görüyorsunuz?"),
            "options": options,
            "correct_answer": options.index(correct),
            "image_url": thumb,
            "explanation": it.get("explanation", ""),
        })
        stats["ok"] += 1
        print(f"  ✓ {kind}: {correct}")

    json.dump(out, open("scripts/questions_gorsel_rich.json", "w"), ensure_ascii=False, indent=2)
    print(f"\nSonuc: {stats} | yazildi: {len(out)} -> scripts/questions_gorsel_rich.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "scripts/gorsel_workflow.json")
