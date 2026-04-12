"""Tests for src/main.py pure formatting functions."""

import pytest

from src.main import (
    clean_response,
    content_to_html,
    extract_action_line,
    markdown_to_html,
)

# --- clean_response ---

class TestCleanResponse:
    @pytest.mark.parametrize("preamble", [
        "I'll search for data",            # I('ll) (search)
        "I will look at listings",          # I( will) (look)
        "I need to search for options",     # I( need to) (search)
        "Let me search the market",         # Let me (search)
        "Let me find recent data",          # Let me (find)
        "Let me check availability",        # Let me (check)
        "Based on my search results",       # Based on (my )(search)
        "Based on the research",            # Based on (the )(research)
        "Perfect. Let me continue",         # Perfect\.?
        "Great. Here we go",                # Great\.?
        "Here's what I found",              # Here('s) what I
        "Here are the listings",            # Here are
        "Searching for current data",       # Searching
        "I found several results",          # I found
        "Unfortunately no results",         # Unfortunately
        "I was unable to locate",           # I was unable
        "I could not find matches",         # I could not
        "However, I notice that",           # However,? I (notice)
        "I notice several trends",          # I notice
        "I'll provide an overview",         # I'll provide
        "I have enough information",        # I have enough information
        "MATCHING YOUR CRITERIA",           # MATCHING YOUR CRITERIA:?$
        "Below is a summary",              # Below (is)
        "Below are the findings",          # Below (are)
        "For today I'll check",            # For today.*I('ll)
        "Based on available data",         # Based on (available)
        "Based on current listings",       # Based on (current)
        "After searching extensively",     # After (searching)
        "After reviewing the data",        # After (reviewing)
    ])
    def test_strips_preamble_line(self, preamble):
        text = f"{preamble}\n- Actual content here"
        result = clean_response(text)
        assert preamble not in result
        assert "Actual content" in result

    def test_strips_separator_lines(self):
        result = clean_response("Data\n---\nMore")
        assert "---" not in result

    def test_collapses_consecutive_blanks(self):
        result = clean_response("A\n\n\n\nB")
        assert result == "A\n\nB"

    def test_passthrough_clean_content(self):
        text = "## Listings\n- Item 1\n- Item 2"
        assert clean_response(text) == text

    def test_empty_string(self):
        assert clean_response("") == ""

    def test_none_input(self):
        assert clean_response(None) == ""


# --- markdown_to_html (src/main.py version) ---

class TestMainMarkdownToHtml:
    """Tests for the simpler markdown_to_html in src/main.py (bold + links + bare URLs)."""

    def test_bold(self):
        result = markdown_to_html("**important**")
        assert "<strong>important</strong>" in result

    def test_markdown_link(self):
        result = markdown_to_html("[text](https://example.com)")
        assert "https://example.com" in result
        assert ">text</a>" in result

    def test_bare_url(self):
        result = markdown_to_html("Visit https://example.com today")
        assert 'href="https://example.com"' in result

    def test_no_formatting(self):
        assert markdown_to_html("plain text") == "plain text"


# --- content_to_html ---

class TestContentToHtml:
    def test_unordered_list(self):
        result = content_to_html("- item 1\n- item 2")
        assert "<ul" in result
        assert "<li" in result
        assert "item 1" in result
        assert "</ul>" in result

    def test_ordered_list(self):
        result = content_to_html("1. first\n2. second")
        assert "<ol" in result
        assert "<li" in result

    def test_h2_header(self):
        result = content_to_html("## Section Title")
        assert "Section Title" in result
        assert "font-weight:700" in result or "font-weight: 700" in result

    def test_h3_header(self):
        result = content_to_html("### Subsection")
        assert "Subsection" in result
        assert "text-transform:uppercase" in result or "text-transform: uppercase" in result

    def test_high_priority_line(self):
        result = content_to_html("HIGH PRIORITY: urgent item")
        assert "#dc2626" in result or "dc2626" in result

    def test_high_priority_red_emoji(self):
        result = content_to_html("🔴 Critical finding")
        assert "#dc2626" in result or "dc2626" in result

    def test_caller_script_line(self):
        result = content_to_html('📞 CALLER SCRIPT: "Hi, my name is Angela..."')
        assert "#EFF6FF" in result or "EFF6FF" in result.upper()

    def test_plain_paragraph(self):
        result = content_to_html("Regular text here")
        assert "<p" in result
        assert "Regular text here" in result

    def test_empty_input(self):
        assert content_to_html("") == ""

    def test_none_input(self):
        assert content_to_html(None) == ""

    def test_list_closes_before_text(self):
        result = content_to_html("- a\n- b\nsome text")
        assert "</ul>" in result
        ul_close = result.index("</ul>")
        text_pos = result.index("some text")
        assert ul_close < text_pos

    def test_preamble_stripped_first(self):
        result = content_to_html("I'll search for data\n- Real item")
        assert "I'll search" not in result
        assert "Real item" in result

    def test_lonely_bullet_markers_skipped(self):
        """Single '-' or '*' without text after should be skipped."""
        result = content_to_html("-\n*\nActual content")
        assert "Actual content" in result


# --- extract_action_line ---

class TestExtractActionLine:
    def test_bold_action_format(self):
        content = "**Action:** Call Zook Cabins at 717-555-1234\n**Why:** Get pricing"
        assert "Call Zook Cabins" in extract_action_line(content)

    def test_truncated_at_160(self):
        long_action = "**Action:** " + "x" * 200
        result = extract_action_line(long_action)
        assert len(result) <= 160

    def test_case_insensitive(self):
        result = extract_action_line("**action:** do something important")
        assert "do something" in result

    def test_fallback_first_meaningful_line(self):
        content = "This is a real task that should be extracted as fallback"
        result = extract_action_line(content)
        assert "real task" in result

    def test_all_short_lines_default(self):
        content = "Hi\nBye\nOk"
        assert extract_action_line(content) == "Today's action item"

    def test_html_stripped_in_fallback(self):
        content = "<div>This is a real task to do today</div>"
        result = extract_action_line(content)
        assert "<div>" not in result
