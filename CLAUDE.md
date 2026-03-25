# Taos Daily Digest — Claude Code Instructions

## Project Overview
Daily email digest for Angela (RECIPIENT_EMAIL_SECRET) tracking the Taos off-grid homestead project.
See `taos-project-context/OPUS_CONTEXT.md` for full project context.

---

## 🔐 Secrets — CRITICAL

This project uses the following secrets. **Never write actual values into any file.**

| Secret | Where it lives | Used in |
|---|---|---|
| `ANTHROPIC_API_KEY` | GitHub Secrets | `src/main.py` via `os.environ` |
| `SENDER_EMAIL` | GitHub Secrets | `src/main.py` via `os.environ` |
| `SENDER_PASSWORD` | GitHub Secrets | `src/main.py` via `os.environ` |
| `GITHUB_TOKEN` | Auto-injected by Actions | `digest_tracker.py`, `parse_feedback.py` |
| `GH_FEEDBACK_TOKEN` | GitHub Secrets | Injected at build time by `feedback-deploy.yml` |

**`GH_FEEDBACK_TOKEN` pattern:**
- Source file `feedback/index.html` always contains `FEEDBACK_PAT_PLACEHOLDER` — never the real token
- The `feedback-deploy.yml` workflow injects the real token at deploy time via `sed`
- The built file goes to `_site/` which is uploaded as a Pages artifact — never committed to git
- If you ever see the actual token value in `feedback/index.html`, that is a security error — revert and rotate the token immediately

---

## Architecture

```
GitHub Actions (7 AM MT daily):
  1. parse_feedback.py       — reads Angela's issue comments → data/context_notes.json
  2. src/main.py             — generates digest email with context injection
  3. Commit data/*.json      — caches only, no secrets

Separate trigger (on push or manual):
  feedback-deploy.yml        — builds feedback form with injected token → GitHub Pages
```

---

## Key Files

| File | Purpose |
|---|---|
| `src/main.py` | Main digest generator — do not add any hardcoded credentials |
| `data/constraints.json` | Project config — safe to edit, no secrets |
| `data/context_notes.json` | Angela's completions — auto-generated, safe to commit |
| `feedback/index.html` | Template only — always has `FEEDBACK_PAT_PLACEHOLDER` |
| `parse_feedback.py` | Reads GitHub Issues for Angela's feedback |
| `digest_tracker.py` | GitHub Issues API wrapper |

---

## Development Rules

1. All API calls go through `os.environ.get("SECRET_NAME")` — no fallback hardcoded values
2. Do not add `print()` or `log()` statements that output secret values
3. Do not commit `data/last_digest.html` — it may contain issue numbers and personal data (already in `.gitignore` if not, add it)
4. Test locally with a `.env` file that is in `.gitignore` — never commit `.env`
5. The `data/` folder only contains safe JSON — no credentials

---

## Angela's Feedback Loop (read before modifying)

Angela clicks "✅ I Did This" in the email → GitHub Pages form (token injected at build time) → posts `COMPLETION_DATA:{...}` comment to that day's tracking issue → `parse_feedback.py` picks it up next morning → injected into AI prompts and dashboard.

Do not change the `COMPLETION_DATA:` comment format without also updating `parse_feedback.py`.
