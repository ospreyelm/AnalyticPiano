# Neon Content Generation Runbook

This runbook describes how to generate HarmonyLab exercise content from a local
checkout while writing the rows directly to a Neon Postgres database.

## What Local Generation Does

Management commands run local Python code and write directly to the database
configured for that shell. There is no local staging step and no upload step.

If `DATABASE_URL` points to Neon, the commands create exercises, playlists,
playlist links, courses, and derived analysis rows in Neon.

Deploying is not required for local generation. Deploy only if Fly/admin
runtime generation should use newly edited command code.

## Shell Setup

Use the settings module that honors `DATABASE_URL`:

```bash
export DJANGO_SETTINGS_MODULE=harmony.settings.common
export AUTHOR='avnerdorman@gmail.com'
export DATABASE_URL='postgresql://neondb_owner:PASSWORD@DIRECT_NEON_HOST/neondb?sslmode=require'
```

Use Neon's direct connection URL for long generation jobs. Avoid the pooler URL
for these commands.

Direct host shape:

```text
ep-...c-7.us-east-1.aws.neon.tech
```

Pooled host shape to avoid for generation:

```text
ep-...-pooler.c-7.us-east-1.aws.neon.tech
```

Quote the full URL. Unquoted `&` query parameters will be interpreted by the
shell as background-job operators.

## Verify Database Connectivity

First confirm the shell has the intended URL:

```bash
echo "$DATABASE_URL" | sed -E 's#(postgresql://[^:]+:)[^@]+#\1****#'
```

Confirm Django is configured for Neon, not local Postgres:

```bash
python3 manage.py shell -c "from django.conf import settings; db=settings.DATABASES['default']; print(db.get('HOST'), db.get('NAME'))"
```

Expected output should show a Neon host and `neondb`.

Confirm a real database query works:

```bash
python3 manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute('select 1'); print(c.fetchone())"
```

Expected:

```text
(1,)
```

If this hangs, test outside Django:

```bash
PGCONNECT_TIMEOUT=5 psql "$DATABASE_URL" -c "select 1;"
```

If `psql` times out on port `5432`, the blocker is network/security software,
VPN, firewall, or Neon connectivity, not Django.

## Prepare Database

Run migrations after connectivity is verified:

```bash
python3 manage.py migrate
```

The CKEditor warning is unrelated to content generation and can be ignored for
this runbook.

Optional before-count:

```bash
python3 manage.py shell -c "from apps.exercises.models import Exercise, Playlist, ExercisePlaylistOrdered; print('before', Exercise.objects.count(), Playlist.objects.count(), ExercisePlaylistOrdered.objects.count())"
```

## Core Early-Unit Generation

```bash
python3 manage.py generate_unit1 --author "$AUTHOR"
python3 manage.py generate_unit2_meter_reference --author "$AUTHOR" --public
python3 manage.py generate_unit2_meter_exercises --author "$AUTHOR" --public
python3 manage.py generate_unit2_barline_exercises --author "$AUTHOR" --public
python3 manage.py generate_unit3_key_sig_exercises --author "$AUTHOR" --public --overwrite
python3 manage.py generate_unit3_scale_exercises --author "$AUTHOR" --public --overwrite
python3 manage.py generate_unit4 --author "$AUTHOR" --public --overwrite
python3 manage.py generate_unit5 --type both --author "$AUTHOR" --public --overwrite
```

`generate_unit1` has no `--public` flag. It creates public Unit 1 content by
default.

Default Unit 1 generation scans `data/corpus/bach` and creates a large reusable
pool. With the current checked-in corpus, expect roughly:

```text
11,190 exercises
6 playlists
up to 216 playlist links
```

The playlists are wired near the end. Seeing thousands of Unit 1 exercises
before playlists appear can be normal.

Smaller Unit 1 dev seed:

```bash
python3 manage.py generate_unit1 --author "$AUTHOR" --file bwv1.6.json --max-per-playlist 6 --max-per-stage 2
```

Rebuild Unit 1 playlists from already-created rows without generating more:

```bash
python3 manage.py generate_unit1 --author "$AUTHOR" --playlist-only
```

## Compendium And Clausulae Generation

```bash
python3 manage.py import_compendium_cadences --author "$AUTHOR" --public --overwrite

python3 manage.py generate_clausulae_b1 --author "$AUTHOR" --public --overwrite
python3 manage.py generate_roman_from_clausulae --author "$AUTHOR" --voices 3 4 --cadence simple compound --unit 9 --public --overwrite
python3 manage.py generate_harmonization_from_clausulae --unit 9 --author "$AUTHOR" --voices 3 --public --overwrite
```

## Bach Unit Playlists

Generate Riemenschneider 1-30 for Roman, figured bass, play, and play-with-figures modes efficiently across all units using the matrix command:

```bash
python3 manage.py generate_bach_unit_matrix \
  --riemenschneider 1-30 \
  --units 9,10,11,12,14,16,17,18,19,20 \
  --modes roman,figures,play,play_figures \
  --author "$AUTHOR" \
  --public
```

To rebuild playlists from existing database rows only (skipping the music21 parse loop and database writes, useful for playlist tuning):

```bash
python3 manage.py generate_bach_unit_matrix \
  --riemenschneider 1-30 \
  --units 9,10,11,12,14,16,17,18,19,20 \
  --modes roman,figures,play,play_figures \
  --author "$AUTHOR" \
  --public \
  --playlist-only \
  --skip-refresh
```

Note: the figured-bass command mode is `figures`, not `figured_bass`.

## Refresh Derived Data

After generation, refresh derived analysis, targets, tags, and knowledge-graph
state:

```bash
python3 manage.py refresh_all_exercises
python3 manage.py backfill_skill_tags --all
python3 manage.py backfill_raw_roman_numeral
python3 manage.py reanalyze_knowledge_graph
```

## Verify Results

```bash
python3 manage.py shell -c "from apps.exercises.models import Exercise, Playlist, ExercisePlaylistOrdered; print('after', Exercise.objects.count(), Playlist.objects.count(), ExercisePlaylistOrdered.objects.count()); print(Playlist.objects.order_by('-created').values_list('id','name','created').first())"
```

To inspect recent playlists:

```bash
python3 manage.py shell -c "from apps.exercises.models import Playlist; print(list(Playlist.objects.order_by('-created').values_list('id','name','created')[:20]))"
```

## Seeing Content In The App

The app must run with the same Neon environment variables:

```bash
export DJANGO_SETTINGS_MODULE=harmony.settings.common
export DATABASE_URL='postgresql://neondb_owner:PASSWORD@DIRECT_NEON_HOST/neondb?sslmode=require'
```

Restart the app server after changing env vars. A running Django process will
not automatically pick up a `DATABASE_URL` exported in another terminal.

Admin-triggered generation in Fly uses Fly's runtime `DATABASE_URL`, not the
local shell. To make Fly admin actions write to Neon, update the Fly app secret
and restart/redeploy the app.

## Common Failure Modes

- `No DATABASE_URL environment variable set`: that terminal is not configured
  for Neon.
- Django prints `localhost analyticpiano`: `harmony.settings.local` is active
  or local settings are overriding the database. Use
  `DJANGO_SETTINGS_MODULE=harmony.settings.common`.
- `psql` timeout on port `5432`: network/security software, VPN, firewall, or
  connectivity is blocking Postgres.
- Shell output like `+ done export DATABASE_URL=`: the URL was not quoted and
  `&` was treated as a shell operator.
- Exercises appear but playlists do not yet: some generators create exercise
  rows first and wire playlists near the end.

## GitHub Actions Automation

A workflow at `.github/workflows/generate-neon-content.yml` allows running the Bach unit matrix generation directly from GitHub Actions on a manual dispatch.

For the workflow to function:
1. Store the direct Neon connection string in GitHub repository secrets as `NEON_DATABASE_URL`.
2. Navigate to **Actions** -> **Generate Neon Content** -> **Run workflow**.
3. Provide the parameters (Riemenschneider range, target units, and modes) and click run.

