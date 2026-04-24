# Fly.io Deployment Design

*Written: 2026-04-24*

---

## Overview

Deploy the app to Fly.io as the production host. The app is already Heroku-ready (`Procfile`, `harmony/settings/heroku.py`, gunicorn, WhiteNoise); this spec adds the four files needed to run on Fly.io instead, at roughly half the cost (~$5–7/mo vs ~$12–16/mo on Heroku).

No application code changes. No new dependencies.

---

## New Files

### `Dockerfile`

Python 3.12 slim base image. Install dependencies via `pipenv install --system --deploy`. Collect static files at build time (`python manage.py collectstatic --noinput`). Expose port 8000. Default command: `gunicorn harmony.wsgi:application --bind 0.0.0.0:8000 --log-file -`.

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
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "harmony.wsgi:application", "--bind", "0.0.0.0:8000", "--log-file", "-"]
```

### `fly.toml`

App config for Fly.io. Key settings:

- Region: `ord` (Chicago) — change to closest region if needed
- Internal port: 8000
- HTTP health check on `/`
- `[deploy] release_command` runs `python manage.py migrate && python manage.py createcachetable` (equivalent to Heroku's `release` dyno)
- Machine: `shared-cpu-1x`, 512MB RAM (upgradeable via `fly scale`)

```toml
app = "APP_NAME"
primary_region = "ord"

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

`APP_NAME` is set at `fly launch` time and becomes the subdomain: `APP_NAME.fly.dev`.

### `harmony/settings/fly.py`

Mirrors `harmony/settings/heroku.py`. Inherits from `common.py`, sets production security flags, reads secrets from environment.

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

`DJANGO_SETTINGS_MODULE=harmony.settings.fly` is set as a Fly secret.

### `.dockerignore`

Prevents large/sensitive local files from being copied into the Docker image:

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

---

## Environment Variables

Set via `fly secrets set KEY=VALUE`. All secrets are encrypted at rest by Fly.io.

| Variable | Value | Notes |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `harmony.settings.fly` | Selects fly settings |
| `SECRET_KEY` | strong random string | Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS` | `["APP_NAME.fly.dev"]` | JSON list; add custom domain when ready |
| `DATABASE_URL` | set automatically | Fly sets this when Postgres is attached |
| `EMAIL_HOST_USER` | Gmail address | Used for Django password reset emails |
| `EMAIL_HOST_PASSWORD` | Gmail app password | Create at myaccount.google.com/apppasswords |
| `SENTRY_DSN` | Sentry project DSN | Optional; omit to disable error tracking |

---

## Deploy Sequence

One-time setup (run once from local machine with `fly` CLI installed):

```bash
# 1. Authenticate
fly auth login

# 2. Create the app (generates fly.toml skeleton — replace with our fly.toml)
fly launch --no-deploy

# 3. Provision Postgres
fly postgres create --name APP_NAME-db

# 4. Attach Postgres (auto-sets DATABASE_URL secret)
fly postgres attach APP_NAME-db

# 5. Set remaining secrets
fly secrets set \
  DJANGO_SETTINGS_MODULE=harmony.settings.fly \
  SECRET_KEY="..." \
  ALLOWED_HOSTS='["APP_NAME.fly.dev"]' \
  EMAIL_HOST_USER="..." \
  EMAIL_HOST_PASSWORD="..."

# 6. Deploy
fly deploy

# 7. Verify
fly open
fly logs
```

Subsequent deploys: `fly deploy` (or push to a CI pipeline).

---

## Database Migration from Heroku

Not automated — one-off manual task after the app is verified live:

```bash
# On old Heroku host
heroku pg:backups:capture --app OLD_APP_NAME
heroku pg:backups:download --app OLD_APP_NAME

# Restore to Fly Postgres
fly postgres connect -a APP_NAME-db  # get connection string
pg_restore --verbose --clean --no-acl --no-owner -d $DATABASE_URL latest.dump
```

Run this after verifying the fresh deploy works with an empty DB (admin login, exercise load).

---

## Custom Domain (Post-Launch)

After verifying the `.fly.dev` domain works:

```bash
fly certs add yourdomain.com
fly certs add www.yourdomain.com
```

Then update DNS at your registrar: `CNAME yourdomain.com → APP_NAME.fly.dev`. Update `ALLOWED_HOSTS` secret to include both domains.

---

## Cost Estimate

| Resource | Cost |
|---|---|
| 1× shared-cpu-1x VM (512MB) | ~$2–4/mo |
| Fly Postgres (1GB shared) | ~$3/mo |
| **Total** | **~$5–7/mo** |

Fly's free allowance (3 shared VMs, 3GB storage) may cover the VM initially. Postgres is always billed.

---

## Out of Scope

- Clerk auth integration (separate spec)
- CI/CD pipeline (manual `fly deploy` sufficient for now)
- S3/CDN for media (WhiteNoise handles static files; no user-uploaded media in app)
- Horizontal scaling (single machine sufficient for pilot load)
