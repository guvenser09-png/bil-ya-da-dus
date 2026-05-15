"""Turkish profanity filter for bio and display names.

Simple keyword-based approach. Catches common Turkish profanity
and offensive terms. Normalized matching (lowercase, no accents).
"""

import re
import unicodedata

# Common Turkish profanity/offensive words (normalized, lowercase)
# This is intentionally kept brief — in production, use a more comprehensive list
_TURKISH_PROFANITY = {
    "amk", "aq", "amq", "amina", "aminakoyim", "aminakoyayim",
    "sik", "sikik", "sikim", "sikerim", "sikeyim", "siktir",
    "orospu", "orosbu", "orospucocugu", "orospucocu",
    "pic", "piç", "pust", "puşt", "ibne",
    "got", "göt", "gotunu", "gotveren",
    "yarrak", "yarak", "yarram",
    "gavat", "pezevenk",
    "mal", "gerizekali", "aptal", "salak", "gerizekâlı",
    "anan", "anani", "ananı", "annen",
    "kahpe", "kaltak",
    "manyak", "deli",
    "haysiyetsiz", "şerefsiz", "serefsiz", "namussuz",
    "dangalak", "gerizekalı",
}

# Additional patterns (regex)
_PROFANITY_PATTERNS = [
    r"a+m+[ıi]+n+a+",  # amına variations
    r"s[ıi]+k+",        # sik variations
    r"o+r+o+s+[pb]+u+", # orospu variations
    r"y+a+r+[ra]+k+",   # yarak variations
]


def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase, remove accents, strip special chars."""
    text = text.lower()
    # Turkish specific char replacements
    text = text.replace("ı", "i").replace("ğ", "g").replace("ş", "s")
    text = text.replace("ç", "c").replace("ö", "o").replace("ü", "u")
    # Remove accents
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


def contains_profanity(text: str) -> bool:
    """Check if text contains Turkish profanity.

    Args:
        text: The text to check (bio, display name, etc.)

    Returns:
        True if profanity is found, False otherwise.
    """
    if not text:
        return False

    normalized = _normalize(text)

    # Remove spaces and special characters for word matching
    cleaned = re.sub(r"[^a-z0-9]", "", normalized)

    # Direct word matching
    words = re.split(r"\s+", normalized)
    for word in words:
        clean_word = re.sub(r"[^a-z]", "", word)
        if clean_word in _TURKISH_PROFANITY:
            return True

    # Check full cleaned text for embedded profanity
    for word in _TURKISH_PROFANITY:
        if word in cleaned:
            return True

    # Pattern matching
    for pattern in _PROFANITY_PATTERNS:
        if re.search(pattern, cleaned):
            return True

    return False


def clean_text(text: str) -> str:
    """Replace profanity with asterisks (for display purposes).

    Args:
        text: The text to clean.

    Returns:
        Text with profanity replaced by asterisks.
    """
    if not text:
        return text

    result = text
    normalized = _normalize(text)

    for word in _TURKISH_PROFANITY:
        if word in _normalize(result):
            # Find and replace in original text (case-insensitive)
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub("*" * len(word), _normalize(result))

    return result
