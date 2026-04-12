"""Tests for research_agent.py clean() function."""

import pytest

from research_agent import clean


class TestClean:
    """Test the clean() preamble/filler stripper."""

    @pytest.mark.parametrize("line", [
        "I'll search for land listings",
        "I found several results",
        "I need to check the database",
        "I searched for available parcels",
        "I discovered new listings",
        "Let me find some options",
        "Based on my search results",
        "Based on the research I conducted",
        "Here's what I found today",
        "Here is what the data shows",
        "Here are the current listings",
        "Below is a summary",
        "Below are the findings",
        "After searching extensively",
        "After reviewing the data",
        "Unfortunately no results",
        "I was unable to find matches",
        "I could not locate any",
        "Searching for current data",
        "Perfect. Moving on",
        "Great. Here we go",
        "For today I'll focus on",
        "I notice several trends",
        "I have enough information",
        "I'll provide an overview",
        "In summary the market is",
        "To summarize the findings",
        "Overall the data shows",
        "In conclusion we see",
    ])
    def test_strips_preamble_pattern(self, line):
        result = clean(f"{line}\n- Actual finding 1")
        assert "Actual finding 1" in result
        assert line not in result

    def test_strips_separator_lines(self):
        """Separator lines are removed entirely (not replaced with blanks)."""
        assert clean("Data\n---\nMore data") == "Data\nMore data"

    def test_strips_asterisk_separators(self):
        assert clean("Data\n****\nMore") == "Data\nMore"

    def test_collapses_consecutive_blanks(self):
        result = clean("A\n\n\n\nB")
        assert result == "A\n\nB"

    def test_empty_input(self):
        assert clean("") == ""

    def test_none_input(self):
        assert clean(None) == ""

    def test_passthrough_clean_text(self):
        text = "## Results\n- Finding 1\n- Finding 2"
        assert clean(text) == text

    def test_case_insensitive(self):
        result = clean("i found several results\nActual data")
        assert "Actual data" in result
        assert "i found" not in result

    def test_preserves_indentation(self):
        """Indented lines are kept but final .strip() trims leading whitespace."""
        text = "Top line\n  - Indented item\n    - Nested item"
        result = clean(text)
        assert "  - Indented item" in result
        assert "    - Nested item" in result
