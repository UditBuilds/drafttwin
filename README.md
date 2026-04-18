# DraftTwin

Multi-brand AI customer support drafting tool for D2C brands. Each brand signs up, onboards a brain file, and gets a private dashboard for drafting + reviewing replies.

## Stack
Python + Flask, Flask-Login, SQLite, vanilla HTML/JS, Anthropic SDK (Claude `claude-sonnet-4-6`). Deployable on Render.

## Local setup

```bash
cd drafttwin
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp .env.example .env     # then edit .env and paste ANTHROPIC_API_KEY
python app.py
```

Open http://localhost:5000.

## Flow

1. `/signup` — email + password. Creates the brand account.
2. `/onboarding` — fill the brand form. Generates `brain.md` v1.0, saves to SQLite + `brains/<id>-<slug>.md`.
3. `/dashboard` — paste a customer DM → structured `{ classification, reply, reasoning }` response. Last 20 drafts appear below with `[Flag this reply]` buttons.
4. `/brain` — edit brain.md section-by-section. Saving bumps the minor version (v1.0 → v1.1 → v1.2). Current version + last-updated shown on dashboard.
5. `/flagged` — review all flagged drafts with customer message, twin's original reply, and your correction. Use this as your gap list when editing the brain.

## Auth & data isolation

- One account per brand (`brands.email` is UNIQUE).
- Every `/dashboard`, `/brain`, `/flagged`, and `/api/*` route is `@login_required`.
- All DB queries are scoped to `current_user.id` — brands cannot see each other's drafts, flags, or brain files.
- Passwords hashed with `werkzeug.security.generate_password_hash` (PBKDF2).

## How the LLM call works

- System prompt = full brand `brain.md` + strict operating rules.
- The brain.md block uses `cache_control: ephemeral` — Anthropic prompt caching means the long brand context is billed/read once per ~5-min window across many DMs.
- Structured output is enforced by a forced `draft_reply` tool call. Classification is constrained to `AUTO | DRAFT+APPROVE | ESCALATE`.

## Brain versioning

Stored as a plain `major.minor` string in `brands.version`. The editor always bumps the minor on save. The parser in `brain_editor.py` splits the brain into 5 fixed sections + internal notes; the assembler regenerates the header/footer with the new version, so the on-disk file stays well-formed regardless of what the founder edits.

## Deploy to Render

Commit this directory to a git repo and push. In Render, "New +" → "Blueprint" → point at the repo. `render.yaml` defines:
- one web service running `gunicorn app:app`
- a 1GB persistent disk mounted at `/var/data` so SQLite survives restarts
- `ANTHROPIC_API_KEY` (set manually), `FLASK_SECRET_KEY` (auto-generated)

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask routes (index, onboarding, dashboard, brain, flagged, API) |
| `auth.py` | Flask-Login wiring, User model, login/signup/logout blueprint |
| `brain_generator.py` | Onboarding form → initial brain.md |
| `brain_editor.py` | Parse/assemble brain.md sections; version bump |
| `llm.py` | Anthropic SDK call, tool use, prompt caching |
| `db.py` | SQLite schema, migrations, query helpers |
| `templates/` | Base, login, signup, onboarding, dashboard, brain, flagged |
| `static/style.css` | Styling |
| `brains/` | Generated brain.md files per brand |
| `render.yaml`, `Procfile` | Render deploy |

## Next phases

- Brain editing: diff view between versions, rollback, import of an external brain.md
- Slack/Telegram notifications for DRAFT+APPROVE / ESCALATE
- "Retrain from flags" — auto-suggest brain edits from flagged examples
