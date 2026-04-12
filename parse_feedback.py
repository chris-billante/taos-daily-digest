#!/usr/bin/env python3
"""
parse_feedback.py — Pre-digest feedback parser for Taos Build Intel.

Runs before src/main.py in GitHub Actions. Reads COMPLETION_DATA comments
from recent tracking issues and writes data/context_notes.json so the
digest generator can inject Angela's notes into AI prompts.

Usage:
    python parse_feedback.py
    GITHUB_TOKEN must be set in environment.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("parse-feedback")

REPO_OWNER = os.environ.get("REPO_OWNER", "chris-billante")
REPO_NAME  = os.environ.get("FEEDBACK_REPO", "taos-feedback-private")
DATA_FILE  = Path(__file__).parent / "data" / "context_notes.json"
LOOKBACK_DAYS = 14  # How many days of issues to check for feedback
NOTES_RETENTION_DAYS = 30  # Keep completions for this many days in context_notes.json

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def github_get(path: str, params: dict = None) -> list | dict | None:
    """Make a GitHub API GET request."""
    if not GITHUB_TOKEN:
        log.error("GITHUB_TOKEN not set — cannot fetch issues")
        return None
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        log.warning(f"GitHub API {r.status_code} for {path}: {r.text[:200]}")
        return None
    except Exception as e:
        log.error(f"GitHub API error ({path}): {e}")
        return None


def get_recent_digest_issues() -> list:
    """Fetch tracking issues from the last LOOKBACK_DAYS days."""
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    issues = github_get("issues", params={
        "labels": "daily-digest,tracking",
        "state": "all",
        "since": since,
        "per_page": LOOKBACK_DAYS + 2,
        "sort": "created",
        "direction": "desc"
    })
    if not issues:
        return []
    log.info(f"Found {len(issues)} tracking issue(s) in last {LOOKBACK_DAYS} days")
    return issues


def get_issue_comments(issue_number: int) -> list:
    """Fetch all comments for a given issue."""
    comments = github_get(f"issues/{issue_number}/comments", params={"per_page": 50})
    return comments or []


def parse_completion_comment(comment_body: str) -> dict | None:
    """
    Extract COMPLETION_DATA JSON from a comment body.
    Format: COMPLETION_DATA:{"completed":true, ...}
    Returns parsed dict or None.
    """
    match = re.search(r'COMPLETION_DATA:(\{.+?\})', comment_body, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        # Validate required fields
        if not isinstance(data, dict):
            return None
        if not data.get("date"):
            return None
        return data
    except json.JSONDecodeError as e:
        log.warning(f"Could not parse COMPLETION_DATA JSON: {e}")
        return None


def build_task_id(date: str, task_summary: str) -> str:
    """Build a stable deduplication key from date + task."""
    summary_slug = re.sub(r'[^a-z0-9]+', '-', task_summary.lower())[:40].strip('-')
    return f"action-{date}-{summary_slug}"


def load_existing_notes() -> dict:
    """Load existing context_notes.json or return empty structure."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "completions" in data:
                    return data
        except (OSError, json.JSONDecodeError) as e:
            log.warning(f"Could not load existing context_notes.json: {e}")
    return {"completions": []}


def save_notes(notes: dict):
    """Write context_notes.json."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2)
    log.info(f"Saved context_notes.json ({len(notes['completions'])} completion(s))")


def prune_old_completions(completions: list) -> list:
    """Remove completions older than NOTES_RETENTION_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NOTES_RETENTION_DAYS)
    kept = []
    for c in completions:
        try:
            date = datetime.fromisoformat(c["date"])
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            if date >= cutoff:
                kept.append(c)
        except (ValueError, KeyError):
            kept.append(c)  # Keep if we can't parse the date
    if len(kept) < len(completions):
        log.info(f"Pruned {len(completions) - len(kept)} old completion(s)")
    return kept


def main():
    log.info("parse_feedback.py starting")

    if not GITHUB_TOKEN:
        log.warning("GITHUB_TOKEN not set — skipping feedback parse (digest will run without context notes)")
        return

    # Load existing notes (preserve history)
    existing = load_existing_notes()
    existing_by_id = {c.get("task_id", ""): c for c in existing["completions"]}

    issues = get_recent_digest_issues()
    if not issues:
        log.info("No tracking issues found — nothing to parse")
        # Still save (may prune old entries)
        existing["completions"] = prune_old_completions(existing["completions"])
        save_notes(existing)
        return

    new_count = 0
    updated_count = 0

    for issue in issues:
        issue_number = issue["number"]
        log.info(f"Checking issue #{issue_number}: {issue['title'][:60]}")

        comments = get_issue_comments(issue_number)
        for comment in comments:
            data = parse_completion_comment(comment.get("body", ""))
            if not data:
                continue

            task_id = build_task_id(
                data.get("date", ""),
                data.get("task_summary", "")
            )
            data["task_id"] = task_id
            data["source_issue_number"] = issue_number

            # Truncate notes defensively
            if data.get("notes"):
                data["notes"] = str(data["notes"])[:500]
            if data.get("follow_up"):
                data["follow_up"] = str(data["follow_up"])[:200]

            # Backward compat: derive status from completed if missing
            if "status" not in data:
                data["status"] = "done" if data.get("completed", True) else "in_progress"

            if task_id in existing_by_id:
                # Update if this comment is newer
                existing_entry = existing_by_id[task_id]
                existing_ts = existing_entry.get("timestamp", "")
                new_ts = data.get("timestamp", "")
                if new_ts > existing_ts:
                    existing_by_id[task_id] = data
                    updated_count += 1
                    log.info(f"  Updated completion for {task_id}")
            else:
                existing_by_id[task_id] = data
                new_count += 1
                log.info(f"  New completion: {data.get('task_summary', '')[:60]}")

    # Rebuild completions list, sorted by date descending
    all_completions = list(existing_by_id.values())
    all_completions.sort(key=lambda c: c.get("date", ""), reverse=True)
    all_completions = prune_old_completions(all_completions)

    result = {"completions": all_completions}
    save_notes(result)

    log.info(f"Done: {new_count} new, {updated_count} updated, "
             f"{len(all_completions)} total completion(s) in context_notes.json")


if __name__ == "__main__":
    main()
