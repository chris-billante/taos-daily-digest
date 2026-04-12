"""Tests for improved_email_formatter.py pure functions."""

import pytest

from improved_email_formatter import (
    extract_search_params,
    markdown_to_html,
    process_lists,
    strip_claude_preamble,
)

# --- strip_claude_preamble ---

class TestStripClaudePreamble:
    @pytest.mark.parametrize("preamble", [
        "I'll search for available land",
        "I searched for listings in Taos",
        "Let me search for options",
        "Here's what I found today",
        "I found the following results",
        "Based on my search results",
        "According to my search data",
        "Here are the results",
        "I've searched extensively",
        "After searching the databases",
    ])
    def test_strips_preamble_patterns(self, preamble):
        text = f"{preamble}\n\n## Actual Content\n- Item 1"
        result = strip_claude_preamble(text)
        assert preamble not in result
        assert "Actual Content" in result

    def test_strips_leading_blank_lines(self):
        result = strip_claude_preamble("\n\n\nContent here")
        assert result == "Content here"

    def test_multiple_preamble_lines(self):
        text = "I'll search for data\nHere's what I found\n\nReal content"
        result = strip_claude_preamble(text)
        assert result.strip().startswith("Real content")

    def test_no_preamble_passthrough(self):
        text = "## Active Listings\n- Item 1\n- Item 2"
        assert strip_claude_preamble(text) == text

    def test_empty_string(self):
        assert strip_claude_preamble("") == ""

    def test_all_preamble_no_content(self):
        text = "I'll search for data\nI found the following results"
        result = strip_claude_preamble(text)
        assert result == ""

    def test_case_insensitive(self):
        text = "i'll search for land\nActual data"
        result = strip_claude_preamble(text)
        assert "Actual data" in result


# --- extract_search_params ---

class TestExtractSearchParams:
    @pytest.mark.parametrize("key,expected_type", [
        ("land listings", "Land Listings"),
        ("builder intelligence", "Builder Intelligence"),
        ("offgrid news", "Offgrid News"),
        ("nm regulatory", "Nm Regulatory"),
        ("van market", "Van Market"),
        ("vehicle search", "Vehicle Search"),
        ("bridge housing", "Bridge Housing"),
    ])
    def test_matches_each_key(self, key, expected_type):
        result = extract_search_params(f"Find {key} in Taos")
        assert result["query_type"] == expected_type
        assert result["search_params"]  # non-empty description

    def test_default_fallback(self):
        result = extract_search_params("completely unrelated prompt text")
        assert result["query_type"] == "General Research"
        assert "market conditions" in result["search_params"]

    def test_returns_dict_with_required_keys(self):
        result = extract_search_params("anything")
        assert "query_type" in result
        assert "search_params" in result


# --- process_lists ---

class TestProcessLists:
    def test_unordered_list(self):
        text = "- item 1\n- item 2"
        result = process_lists(text)
        assert "<ul>" in result
        assert "<li>item 1</li>" in result
        assert "<li>item 2</li>" in result
        assert "</ul>" in result

    def test_ordered_list(self):
        text = "1. first\n2. second"
        result = process_lists(text)
        assert "<ol>" in result
        assert "<li>first</li>" in result
        assert "<li>second</li>" in result

    def test_nested_list(self):
        text = "- top\n  - nested"
        result = process_lists(text)
        assert result.count("<ul>") == 2
        assert result.count("</ul>") == 2

    def test_non_list_content_closes_list(self):
        text = "- item\nplain text"
        result = process_lists(text)
        assert "</ul>" in result
        idx_close = result.index("</ul>")
        idx_text = result.index("plain text")
        assert idx_close < idx_text

    def test_star_bullet(self):
        text = "* item with star"
        result = process_lists(text)
        assert "<li>item with star</li>" in result

    def test_plus_bullet(self):
        text = "+ item with plus"
        result = process_lists(text)
        assert "<li>item with plus</li>" in result

    def test_no_lists_passthrough(self):
        text = "Just plain text here"
        result = process_lists(text)
        assert result == text

    def test_empty_string(self):
        assert process_lists("") == ""


# --- markdown_to_html ---

class TestMarkdownToHtml:
    def test_h1(self):
        result = markdown_to_html("# Title")
        assert "<h1>Title</h1>" in result

    def test_h2(self):
        result = markdown_to_html("## Subtitle")
        assert "<h2>Subtitle</h2>" in result

    def test_h3(self):
        result = markdown_to_html("### Section")
        assert "<h3>Section</h3>" in result

    def test_h4(self):
        result = markdown_to_html("#### Subsection")
        assert "<h4>Subsection</h4>" in result

    def test_bold(self):
        result = markdown_to_html("**bold text**")
        assert "<strong>bold text</strong>" in result

    def test_italic(self):
        result = markdown_to_html("*italic text*")
        assert "<em>italic text</em>" in result

    def test_bold_italic(self):
        result = markdown_to_html("***both***")
        assert "<strong><em>both</em></strong>" in result

    def test_underscore_bold(self):
        result = markdown_to_html("__bold__")
        assert "<strong>bold</strong>" in result

    def test_underscore_italic(self):
        result = markdown_to_html("_italic_")
        assert "<em>italic</em>" in result

    def test_link(self):
        result = markdown_to_html("[click](http://example.com)")
        assert '<a href="http://example.com">click</a>' in result

    def test_code_block(self):
        result = markdown_to_html("```python\nprint('hi')\n```")
        assert "<pre><code>" in result
        assert "print('hi')" in result

    def test_plain_text_wrapped_in_p(self):
        result = markdown_to_html("plain text")
        assert "<p>plain text</p>" in result

    def test_html_not_double_wrapped(self):
        """Lines already starting with < should not be wrapped in <p>."""
        result = markdown_to_html("<div>existing</div>")
        assert "<p><div>" not in result

    def test_excessive_blanks_collapsed(self):
        result = markdown_to_html("a\n\n\n\n\nb")
        assert "\n\n\n" not in result
