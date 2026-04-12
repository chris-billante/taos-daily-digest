"""Tests for table_and_fallback_fixes.py pure functions."""

import pytest

from table_and_fallback_fixes import (
    build_data_table,
    build_email_safe_card,
    format_learning_resources,
    get_learning_resources_for_day,
)

# --- build_email_safe_card ---

class TestBuildEmailSafeCard:
    def test_high_priority_color(self):
        html = build_email_safe_card("Title", "Content", "high")
        assert "#e74c3c" in html

    def test_medium_priority_color(self):
        html = build_email_safe_card("Title", "Content", "medium")
        assert "#f39c12" in html

    def test_low_priority_color(self):
        html = build_email_safe_card("Title", "Content", "low")
        assert "#95a5a6" in html

    def test_default_priority_is_medium(self):
        html = build_email_safe_card("Title", "Content")
        assert "#f39c12" in html

    def test_unknown_priority_falls_back(self):
        html = build_email_safe_card("Title", "Content", "unknown")
        assert "#f39c12" in html

    def test_title_in_output(self):
        html = build_email_safe_card("My Title", "stuff")
        assert "My Title" in html

    def test_content_in_output(self):
        html = build_email_safe_card("T", "Hello world")
        assert "Hello world" in html

    def test_table_structure(self):
        html = build_email_safe_card("T", "C")
        assert "<table" in html
        assert "</table>" in html


# --- build_data_table ---

class TestBuildDataTable:
    def test_headers_rendered(self):
        html = build_data_table(["Col A", "Col B"], [])
        assert "Col A" in html
        assert "Col B" in html
        assert "<th" in html

    def test_rows_rendered(self):
        html = build_data_table(["Col"], [["val1"], ["val2"]])
        assert "val1" in html
        assert "val2" in html

    def test_alternating_row_colors(self):
        html = build_data_table(["Col"], [["r1"], ["r2"], ["r3"]])
        assert "#f8f9fa" in html  # even rows
        assert "white" in html    # odd rows

    def test_empty_rows(self):
        html = build_data_table(["Col"], [])
        assert "<th" in html
        assert "<td" not in html

    def test_multi_column(self):
        html = build_data_table(["A", "B", "C"], [["1", "2", "3"]])
        assert "1" in html
        assert "2" in html
        assert "3" in html


# --- get_learning_resources_for_day ---

class TestGetLearningResourcesForDay:
    @pytest.mark.parametrize("day", [
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    ])
    def test_returns_data_for_each_weekday(self, day):
        result = get_learning_resources_for_day(day)
        assert "topic" in result
        assert "resources" in result
        assert len(result["resources"]) > 0

    def test_monday_topic(self):
        result = get_learning_resources_for_day("monday")
        assert result["topic"] == "Off-Grid Solar Basics"

    def test_case_insensitive(self):
        result = get_learning_resources_for_day("FRIDAY")
        assert "topic" in result

    def test_invalid_day_falls_back_to_monday(self):
        result = get_learning_resources_for_day("notaday")
        assert result["topic"] == "Off-Grid Solar Basics"

    def test_resources_have_required_keys(self):
        result = get_learning_resources_for_day("monday")
        for resource in result["resources"]:
            assert "title" in resource
            assert "url" in resource
            assert "description" in resource
            assert "type" in resource


# --- format_learning_resources ---

class TestFormatLearningResources:
    def test_contains_topic(self):
        data = get_learning_resources_for_day("monday")
        html = format_learning_resources(data)
        assert "Off-Grid Solar Basics" in html

    def test_contains_resource_titles(self):
        data = get_learning_resources_for_day("monday")
        html = format_learning_resources(data)
        for resource in data["resources"]:
            assert resource["title"] in html

    def test_contains_visit_resource_links(self):
        data = get_learning_resources_for_day("monday")
        html = format_learning_resources(data)
        assert "Visit Resource" in html

    def test_contains_urls(self):
        data = get_learning_resources_for_day("monday")
        html = format_learning_resources(data)
        for resource in data["resources"]:
            assert resource["url"] in html

    def test_table_structure(self):
        data = get_learning_resources_for_day("monday")
        html = format_learning_resources(data)
        assert "<table" in html
