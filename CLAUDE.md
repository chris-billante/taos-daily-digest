# Taos Daily Digest — Claude Code Instructions

## Project Overview
Daily email digest for Angela (RECIPIENT_EMAIL_SECRET) tracking the Taos off-grid homestead project.
Project constraints (budget, land criteria, builders, off-grid systems) are loaded from the `PROJECT_CONSTRAINTS` GitHub Secret (base64-encoded JSON) at runtime. For local dev, place a `data/constraints.json` file (gitignored). See `data/constraints.example.json` for the schema.

---

## 🔐 Secrets — CRITICAL

This project uses the following secrets. **Never write actual values into any file.**

| Secret | Where it lives | Used in |
|---|---|---|
| `ANTHROPIC_API_KEY` | GitHub Secrets | `src/main.py` via `os.environ` |
| `SENDER_EMAIL` | GitHub Secrets | `src/main.py` via `os.environ` |
| `SENDER_PASSWORD` | GitHub Secrets | `src/main.py` via `os.environ` |
| `PROJECT_CONSTRAINTS` | GitHub Secrets | Base64-encoded JSON — decoded at runtime by `src/main.py` and `research_agent.py` |
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
| `src/main.py` | Main digest generator — no hardcoded credentials or sensitive data |
| `data/constraints.json` | Local dev only — gitignored, contains sensitive project data |
| `data/constraints.example.json` | Schema reference with placeholder values — safe to commit |
| `data/context_notes.json` | Angela's completions — auto-generated, safe to commit |
| `feedback/index.html` | Template only — always has `FEEDBACK_PAT_PLACEHOLDER` |
| `parse_feedback.py` | Reads GitHub Issues for Angela's feedback |
| `digest_tracker.py` | GitHub Issues API wrapper |

---

## Development Rules

1. All API calls go through `os.environ.get("SECRET_NAME")` — no fallback hardcoded values
2. **Never hardcode sensitive data in prompt strings** — budget, phone numbers, contact names, pricing must come from CONSTRAINTS (loaded from `PROJECT_CONSTRAINTS` env var or `data/constraints.json`)
3. Do not add `print()` or `log()` statements that output secret values
4. Do not commit `data/last_digest.html` — it may contain issue numbers and personal data (already in `.gitignore` if not, add it)
5. Do not commit `data/constraints.json` — it contains sensitive financial and contact data (gitignored)
6. Test locally with a `.env` file that is in `.gitignore` — never commit `.env`
7. The `data/` folder committed files are caches only — no credentials or sensitive data

---

## Angela's Feedback Loop (read before modifying)

Angela clicks "✅ I Did This" in the email → GitHub Pages form (token injected at build time) → posts `COMPLETION_DATA:{...}` comment to that day's tracking issue → `parse_feedback.py` picks it up next morning → injected into AI prompts and dashboard.

Do not change the `COMPLETION_DATA:` comment format without also updating `parse_feedback.py`.
