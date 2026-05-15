"""Tests for Turkish profanity filter."""

import pytest

from app.utils.profanity import contains_profanity, clean_text


class TestContainsProfanity:
    """Test profanity detection."""

    def test_clean_text_is_ok(self):
        """Normal text should not be flagged."""
        assert contains_profanity("Merhaba dünya") is False
        assert contains_profanity("Trivia oyunu seviyorum") is False
        assert contains_profanity("") is False

    def test_none_text_is_ok(self):
        """None should not be flagged."""
        assert contains_profanity(None) is False

    def test_detects_direct_profanity(self):
        """Direct profanity words are detected."""
        assert contains_profanity("siktir") is True
        assert contains_profanity("orospu") is True

    def test_detects_profanity_in_sentence(self):
        """Profanity embedded in a sentence is detected."""
        assert contains_profanity("bu çok siktir bir durum") is True

    def test_detects_case_insensitive(self):
        """Case variations are detected."""
        assert contains_profanity("SiKtIr") is True
        assert contains_profanity("OROSPU") is True

    def test_emoji_and_special_chars_are_ok(self):
        """Emojis and special characters should not be flagged."""
        assert contains_profanity("🎮🔥💪") is False
        assert contains_profanity("harika!!! 🎉") is False

    def test_turkish_chars_normalized(self):
        """Turkish special characters are normalized for matching."""
        assert contains_profanity("şerefsiz") is True
        assert contains_profanity("serefsiz") is True


class TestCleanText:
    """Test profanity cleaning."""

    def test_clean_normal_text(self):
        """Normal text should pass through unchanged."""
        assert clean_text("Merhaba dünya") is not None

    def test_clean_none(self):
        """None should be returned as-is."""
        assert clean_text(None) is None

    def test_clean_empty(self):
        """Empty string should pass through."""
        assert clean_text("") == ""
