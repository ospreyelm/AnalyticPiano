# Fly.io Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the app to Fly.io by adding four config files and a production settings module — zero application code changes.

**Architecture:** Docker image built from `python:3.12-slim`, deps installed via pipenv, static files collected at build time. `fly.toml` routes HTTP traffic to gunicorn on port 8000; a `release_command` runs migrations before each deploy. `harmony/settings/fly.py` mirrors `heroku.py` exactly.

**Tech Stack:** Python 3.12, Django 5.2, gunicorn, WhiteNoise, Postgres (dj-database-url ≥2.0), Fly.io CLI (`flyctl`)

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `Dockerfile` | Create | Build image: install deps, collectstatic, run gunicorn |
| `.dockerignore` | Create | Exclude git, sqlite, cache, corpus data from image |
| `fly.toml` | Create | Fly.io app config: region, port, release command, VM size |
| `harmony/settings/fly.py` | Create | Production settings (mirrors heroku.py) |

---

## Task 1: Create `.dockerignore`

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore`**

```
.git
.env
db.sqlite3
__pycache__
*.pyc
*.pyo
.superpowers
scratch
data/corpus
```

- [ ] **Step 2: Verify it exists**

```bash
cat .dockerignore
```

Expected: the 9 lines above.

- [ ] **Step 3: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore for Fly.io deployment"
```

---

## Task 2: Create `harmony/settings/fly.py`

**Files:**
- Create: `harmony/settings/fly.py`
- Reference: `harmony/settings/heroku.py` (identical structure)

- [ ] **Step 1: Create the settings file**

```python
import os
import json
from harmony.settings.common import *

DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = json.loads(os.environ.get("ALLOWED_HOSTS", "[]"))

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=ENVIRONMENT_PROD,
        traces_sample_rate=1.0,
        send_default_pii=True,
    )
```

- [ ] **Step 2: Verify it imports cleanly with dummy env vars**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.fly \
SECRET_KEY=test \
DATABASE_URL=sqlite:///tmp/test.db \
ALLOWED_HOSTS='[]' \
python -c "import django; django.setup(); print('OK')"
```

Expected output: `OK` (no import errors or tracebacks).

- [ ] **Step 3: Commit**

```bash
git add harmony/settings/fly.py
git commit -m "chore: add Fly.io production settings module"
```

---

## Task 3: Create `Dockerfile`

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create the Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY . .

RUN DJANGO_SETTINGS_MODULE=harmony.settings.fly \
    SECRET_KEY=build-placeholder \
    DATABASE_URL=sqlite:///tmp/build.db \
    ALLOWED_HOSTS='[]' \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "harmony.wsgi:application", "--bind", "0.0.0.0:8000", "--log-file", "-"]
```

Note: `SECRET_KEY`, `DATABASE_URL`, and `ALLOWED_HOSTS` are build-time dummies only — they are never used at runtime. Real values come from `fly secrets`.

- [ ] **Step 2: Build the image locally to verify it works**

```bash
docker build -t harmonylab-test .
```

Expected: build completes without error. The `collectstatic` step should print files being copied. If Docker is not installed locally, skip to Task 4 and let `fly deploy` catch build errors.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "chore: add Dockerfile for Fly.io deployment"
```

---

## Task 4: Create `fly.toml`

**Files:**
- Create: `fly.toml`

- [ ] **Step 1: Install the Fly CLI if not already installed**

```bash
brew install flyctl
# or: curl -L https://fly.io/install.sh | sh
fly version
```

Expected: version string like `fly v0.x.x`.

- [ ] **Step 2: Authenticate**

```bash
fly auth login
```

Opens browser. Complete login. Then:

```bash
fly auth whoami
```

Expected: your email address.

- [ ] **Step 3: Create the Fly app (generates app name)**

```bash
fly launch --no-deploy
```

When prompted:
- Choose an app name (becomes `APP_NAME.fly.dev`) — this is your app's public name for now, changeable later
- Choose region: `ewr` (Newark, Eastern US) or whichever is closest
- **Say NO** when asked to create a Postgres database (we do that separately)
- **Say NO** when asked to deploy now

This creates a `fly.toml` with the generated app name. We will overwrite it in the next step.

- [ ] **Step 4: Replace `fly.toml` with the final config**

Replace the generated `fly.toml` entirely with this content (substitute `APP_NAME` with the name chosen above):

```toml
app = "APP_NAME"
primary_region = "ewr"

[build]

[deploy]
  release_command = "python manage.py migrate && python manage.py createcachetable"

[env]
  PORT = "8000"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

- [ ] **Step 5: Commit**

```bash
git add fly.toml
git commit -m "chore: add fly.toml for Fly.io deployment"
```

---

## Task 5: Provision Postgres and Set Secrets

This task runs CLI commands only — no files changed.

- [ ] **Step 1: Create Fly Postgres cluster**

```bash
fly postgres create --name APP_NAME-db
```

When prompted, choose:
- Region: same as app (`ewr`)
- Configuration: `Development` (single node, cheapest, ~$3/mo)

Wait for provisioning to complete (1–2 minutes).

- [ ] **Step 2: Attach Postgres to the app (auto-sets DATABASE_URL)**

```bash
fly postgres attach APP_NAME-db --app APP_NAME
```

Expected output includes: `Set secret DATABASE_URL`.

- [ ] **Step 3: Generate a strong SECRET_KEY**

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copy the output — use it in the next step.

- [ ] **Step 4: Set remaining secrets**

```bash
fly secrets set \
  DJANGO_SETTINGS_MODULE=harmony.settings.fly \
  SECRET_KEY="PASTE_GENERATED_KEY_HERE" \
  ALLOWED_HOSTS='["APP_NAME.fly.dev"]' \
  EMAIL_HOST_USER="YOUR_GMAIL_ADDRESS" \
  EMAIL_HOST_PASSWORD="YOUR_GMAIL_APP_PASSWORD" \
  --app APP_NAME
```

To create a Gmail app password: Google Account → Security → 2-Step Verification → App passwords. Generate one named "HarmonyLab".

- [ ] **Step 5: Verify secrets are set**

```bash
fly secrets list --app APP_NAME
```

Expected: 6 secrets listed (`DATABASE_URL`, `DJANGO_SETTINGS_MODULE`, `SECRET_KEY`, `ALLOWED_HOSTS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`).

---

## Task 6: Deploy and Verify

- [ ] **Step 1: Deploy**

```bash
fly deploy --app APP_NAME
```

Watch the output. It will:
1. Build the Docker image (2–4 minutes first time)
2. Run `release_command` (migrations + createcachetable)
3. Start the VM

Expected final line: `Visit your newly deployed app at https://APP_NAME.fly.dev/`

If the build fails, check:
- `fly logs --app APP_NAME` for Python tracebacks
- Most common issue: missing env var at collectstatic time (check Task 3 Step 1 dummy vars are present)

- [ ] **Step 2: Open the app**

```bash
fly open --app APP_NAME
```

Expected: browser opens to the app's home page without errors.

- [ ] **Step 3: Create a superuser**

```bash
fly ssh console --app APP_NAME
# inside the container:
python manage.py createsuperuser
```

Follow prompts to create an admin account.

- [ ] **Step 4: Smoke test**

Visit these URLs manually:

| URL | Expected |
|---|---|
| `https://APP_NAME.fly.dev/` | App home page loads |
| `https://APP_NAME.fly.dev/accounts/login/` | Login form renders |
| `https://APP_NAME.fly.dev/analytic-piano-app-admin/` | Django admin login page |

Log in to admin with the superuser created above. Verify the admin panel loads.

- [ ] **Step 5: Verify email (password reset)**

Visit `https://APP_NAME.fly.dev/accounts/reset-password/` and submit your email. Verify a reset email arrives. If not, check:

```bash
fly logs --app APP_NAME | grep -i email
```

Common issue: Gmail "less secure apps" — must use an App Password (not your account password).

- [ ] **Step 6: Tag release**

```bash
git tag deploy/fly-initial
git push origin deploy/fly-initial
```

---

## Task 7: (Optional) Restore Heroku Database

Run this only after Task 6 smoke test passes with an empty DB.

- [ ] **Step 1: Capture and download Heroku backup**

```bash
heroku pg:backups:capture --app OLD_HEROKU_APP_NAME
heroku pg:backups:download --app OLD_HEROKU_APP_NAME
# Downloads as latest.dump
```

- [ ] **Step 2: Get Fly Postgres connection string**

```bash
fly postgres connect -a APP_NAME-db --app APP_NAME
# \q to exit psql
```

The connection string is in the format: `postgres://USER:PASS@HOST:PORT/DB`

```bash
fly secrets list --app APP_NAME | grep DATABASE_URL
# or: fly ssh console -a APP_NAME -C "echo \$DATABASE_URL"
```

- [ ] **Step 3: Restore**

```bash
pg_restore --verbose --clean --no-acl --no-owner \
  -d "$(fly ssh console -a APP_NAME -C 'echo $DATABASE_URL' 2>/dev/null | tr -d '\r')" \
  latest.dump
```

If direct restore fails due to network/SSL, use `fly proxy` to tunnel first:

```bash
fly proxy 15432:5432 -a APP_NAME-db &
pg_restore --verbose --clean --no-acl --no-owner \
  -d "postgres://USER:PASS@localhost:15432/DB" \
  latest.dump
```

- [ ] **Step 4: Verify data**

```bash
fly ssh console --app APP_NAME
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.count(), 'users')"
```

Expected: count matching old Heroku DB.
