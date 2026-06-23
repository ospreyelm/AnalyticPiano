---
name: run-harmonylab
description: Build, run, and drive the HarmonyLab/Monteverdi Django app. Use when asked to start the server, run the test suite, take a screenshot of an exercise or the student dashboard, or check that a frontend (JS) change renders correctly in the browser.
---

Django app served on localhost. Drive it via the gstack `browse` binary
(`~/.claude/skills/gstack/browse/dist/browse`) — this project's CLAUDE.md
mandates `/browse` for all web browsing, and it's already a working
playwright-backed headless Chromium, so there's no need for a separate
driver script.

All paths below are relative to the repo root (or worktree root — this
works identically in a worktree).

## Prerequisites

- Local Postgres running, with a database named `analyticpiano` owned by
  your macOS username (see `harmony/settings/local.py` — `USER` is your
  OS username, not `postgres`). Verify: `pg_isready`.
- Python 3.12, managed via `pipenv` (see `Pipfile`).
- `bun` on PATH (`~/.bun/bin`) — required by gstack's `browse` binary, not
  by the Django app itself.

## Setup

Standard path:

```bash
pipenv install
```

**Faster, if you already have a working venv from another checkout of
this same repo** (e.g. the main checkout, before creating a worktree) and
the `Pipfile` hasn't changed: reuse it instead of reinstalling. `pipenv`
hashes the venv path by directory, so a fresh worktree gets a *new* venv
on `pipenv install` even though the dependencies are identical — skip
that by finding the other checkout's venv and invoking its `python`
directly:

```bash
# from the OTHER checkout that already has a working venv:
pipenv --venv
# -> e.g. /Users/you/.local/share/virtualenvs/HarmonyLab-1-XXXXXXXX
# then from THIS worktree:
/Users/you/.local/share/virtualenvs/HarmonyLab-1-XXXXXXXX/bin/python manage.py <command>
```

## Run (agent path)

```bash
VENV=$(cd /path/to/a/checkout/with/working/venv && pipenv --venv 2>/dev/null) # or pipenv install here
PORT=8123
DJANGO_SETTINGS_MODULE=harmony.settings.local nohup "$VENV/bin/python" manage.py runserver 127.0.0.1:$PORT > /tmp/harmonylab-runserver.log 2>&1 &
echo $! > /tmp/harmonylab-runserver.pid
timeout 20 bash -c 'until curl -sf -o /dev/null http://127.0.0.1:8123/s/login/; do sleep 0.5; done'
```

Stop with `kill $(cat /tmp/harmonylab-runserver.pid)`.

Drive it with gstack `browse` (requires `bun` on PATH):

```bash
export PATH="$HOME/.bun/bin:$PATH"
B=~/.claude/skills/gstack/browse/dist/browse

$B goto http://127.0.0.1:8123/s/login/
$B wait --networkidle
$B fill 'input[name="email"]' "test-student@local.test"
$B fill 'input[name="password"]' "test-student-local-only"
$B click 'button[type="submit"]'
$B wait --load
$B screenshot /tmp/run-skill-shots/after_login.png
$B console --errors
```

If there's no test student yet, create one (local DB only, harmless to
re-run — `get_or_create`):

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local "$VENV/bin/python" manage.py shell <<'PYEOF'
from apps.accounts.models import User, ROLE_STUDENT
u, _ = User.objects.get_or_create(email="test-student@local.test", defaults={"role": ROLE_STUDENT})
u.set_password("test-student-local-only")
u.role = ROLE_STUDENT
u.is_active = True
u.save()
PYEOF
```

The dashboard at `/s/` shows the curriculum tree. A fresh student has
everything locked except Tier 1 ("Start here →" links) — use `browse
snapshot` to get clickable `@e` refs for accordion sections and links
rather than guessing CSS selectors; the tree is built from collapsed
`[button]` rows that need a click to expand before their child links
exist in the DOM.

Screenshots from `browse screenshot` must be written inside the repo/
worktree directory or under `/private/tmp` — other paths (e.g. a job's
own scratch dir outside those two) are rejected.

## Run (human path)

Per `README.md`:

```sh
export DJANGO_SETTINGS_MODULE="harmony.settings.local"
./manage.py runserver
```

Open `http://127.0.0.1:8000`. Ctrl-C to stop.

## Test

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local "$VENV/bin/python" -m pytest
```

802 tests collected (`apps/exercises/tests`, `scripts/tests`) as of this
writing. JS-side tests are plain Node, no runner needed — see
`find lab/static/js -name "*.test.js"`; each runs standalone via
`node <path>.test.js`.

## Gotchas

- **Use `browse wait --networkidle` after `goto`, not `wait --load`.**
  `wait --load` reliably races the form's interactivity — `fill` on a
  visibly-rendered, autofocused input times out (verified: failed 2/2 with
  `--load`, succeeded 3/3 with `--networkidle`, same selectors, same page).
- **`manage.py`'s default `DJANGO_SETTINGS_MODULE` is `harmony.settings.dev`,
  not `local`** — `dev` has no working `SECRET_KEY` fallback and crashes
  with `ImproperlyConfigured: The SECRET_KEY setting must not be empty`.
  Nothing auto-loads `.env` early enough to fix this before Django
  resolves the settings module, so you must export
  `DJANGO_SETTINGS_MODULE=harmony.settings.local` explicitly on every
  `manage.py` invocation in a worktree — copying `.env` from the main
  checkout does **not** fix this by itself (verified: launch still works
  with `.env` absent, as long as the env var is exported inline).
- **`pipenv --venv` is per-directory-path-hashed** — a new worktree does
  not inherit the main checkout's venv automatically. Reusing the other
  checkout's `python` binary directly (see Setup) avoids a multi-minute
  reinstall when the `Pipfile` is unchanged.
- **DB user is your macOS username, not `postgres`** — `harmony/settings/local.py`
  hardcodes this. `pg_isready` alone doesn't tell you the role exists;
  if `manage.py check` fails on auth, the DB role is the first thing to
  check.
