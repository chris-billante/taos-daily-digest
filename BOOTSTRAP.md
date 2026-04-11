# Fresh Session Bootstrap Prompt

Copy everything below the line and paste it as your first message in a new Claude Code session on any computer.

---

## Bootstrap: Taos Daily Digest

I'm starting a fresh Claude Code session on a new/different computer for the `taos-daily-digest` project. Please:

1. **Read the project context**: Read `CLAUDE.md` in this repo root, then `taos-project-context/OPUS_CONTEXT.md` and `data/constraints.json` to understand the project.

2. **Check global standards**: Look for `~/.claude/standards/` — if the directory is empty or missing, recreate it from the reference docs below. If it exists, skip this step.

3. **Check global CLAUDE.md**: Read `~/.claude/CLAUDE.md` — if it doesn't reference the standards directories, update it with the standards directory paths and tool inventory section.

4. **Verify repo health**: Run `git status`, check if there are uncommitted changes, and do a quick `python -m py_compile src/main.py` to confirm the code compiles.

5. **Check recent Actions runs**: Run `gh run list --limit 3` to see if the daily digest is running successfully.

6. **Summarize**: Tell me the current state — what's working, what's broken, and what's pending.

### Standards to recreate if missing (~/.claude/standards/)

If the standards directory doesn't exist, create these 4 files:

- `~/.claude/standards/github-cli/REFERENCE.md` — gh CLI expert reference (all subcommands, --json/--jq filtering, gh api patterns, installed extensions: copilot, actions-cache, dash, poi)
- `~/.claude/standards/github-actions/REFERENCE.md` — Workflow standards (explicit permissions, timeout-minutes, step names, script injection hardening, debugging with gh run view --log-failed)
- `~/.claude/standards/coding-standards/REFERENCE.md` — Python (PEP 8, type hints, pathlib, f-strings), JS (const, strict equality), HTML/Email (WCAG 2.1 AA, 44px tap targets, inline styles), Shell (set -euo pipefail, quote vars)
- `~/.claude/standards/security/REFERENCE.md` — Secret management (env vars only, placeholder pattern, pre-commit checklist), OWASP awareness, incident response

### Key architecture notes

- `src/main.py` generates daily email digest via Anthropic API + SMTP
- `parse_feedback.py` reads feedback from private repo `taos-feedback-private` (not this public repo)
- `feedback/index.html` is a template — always has `FEEDBACK_PAT_PLACEHOLDER`, real token injected at deploy time by `feedback-deploy.yml`
- All secrets are in GitHub Secrets, never in code
- Feedback data flows: email button → GitHub Pages form → private repo issue comment → parse_feedback.py → context injection

### GitHub Secrets (never write these values anywhere)

- `ANTHROPIC_API_KEY`, `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL`, `GITHUB_TOKEN` (auto), `GH_FEEDBACK_TOKEN`

### Installed tools to verify

- `gh` (GitHub CLI), `gh copilot`, `gh actions-cache`, `gh dash`, `gh poi`, `git filter-repo`
