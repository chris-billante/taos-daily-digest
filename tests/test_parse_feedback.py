"""Tests for parse_feedback.py pure helper functions."""

import json

from parse_feedback import build_task_id, parse_completion_comment

# --- parse_completion_comment ---

class TestParseCompletionComment:
    def test_valid_json(self):
        body = 'COMPLETION_DATA:{"completed":true,"date":"2026-04-10"}'
        result = parse_completion_comment(body)
        assert result["completed"] is True
        assert result["date"] == "2026-04-10"

    def test_with_surrounding_text(self):
        body = "Great work!\nCOMPLETION_DATA:{\"date\":\"2026-04-10\",\"status\":\"done\"}\nThanks"
        result = parse_completion_comment(body)
        assert result["date"] == "2026-04-10"

    def test_missing_date_returns_none(self):
        body = 'COMPLETION_DATA:{"completed":true}'
        assert parse_completion_comment(body) is None

    def test_invalid_json_returns_none(self):
        body = "COMPLETION_DATA:{bad json here}"
        assert parse_completion_comment(body) is None

    def test_no_marker_returns_none(self):
        assert parse_completion_comment("Just a regular comment") is None

    def test_non_dict_json_returns_none(self):
        body = "COMPLETION_DATA:[1,2,3]"
        assert parse_completion_comment(body) is None

    def test_empty_body(self):
        assert parse_completion_comment("") is None

    def test_complex_data(self):
        data = {
            "completed": True,
            "date": "2026-04-10",
            "status": "done",
            "task_summary": "Call Zook Cabins",
            "notes": "Got a quote for $213K",
            "follow_up": "Check delivery schedule",
        }
        body = f"COMPLETION_DATA:{json.dumps(data)}"
        result = parse_completion_comment(body)
        assert result["notes"] == "Got a quote for $213K"
        assert result["follow_up"] == "Check delivery schedule"

    def test_empty_date_returns_none(self):
        body = 'COMPLETION_DATA:{"date":"","completed":true}'
        assert parse_completion_comment(body) is None


# --- build_task_id ---

class TestBuildTaskId:
    def test_basic(self):
        result = build_task_id("2026-04-10", "Call Zook Cabins")
        assert result == "action-2026-04-10-call-zook-cabins"

    def test_special_chars_stripped(self):
        result = build_task_id("2026-04-10", "Check $$$pricing!!!")
        assert "$" not in result
        assert "!" not in result
        assert result.startswith("action-2026-04-10-")

    def test_truncation(self):
        long_summary = "a" * 60
        result = build_task_id("2026-04-10", long_summary)
        slug = result.replace("action-2026-04-10-", "")
        assert len(slug) <= 40

    def test_deterministic(self):
        a = build_task_id("2026-04-10", "Same task")
        b = build_task_id("2026-04-10", "Same task")
        assert a == b

    def test_trailing_hyphens_stripped(self):
        result = build_task_id("2026-04-10", "test!!!")
        assert not result.endswith("-")
