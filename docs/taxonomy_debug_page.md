# Taxonomy Debug Page

## Overview

A staff-only Django debug page is available for browsing the live curriculum taxonomy in a human-readable format.

Route:

```text
/dashboard/debug/taxonomy/
```

With the local dev server running, the full URL is:

```text
http://127.0.0.1:8000/dashboard/debug/taxonomy/
```

This page reads directly from:

```text
music_theory_taxonomy_with_branches.json
```

It is intended as a live inspection tool while refining unit titles, sequencing, terminology, tags, and analysis payloads.

## Access Rules

- Requires authentication
- Requires a staff user (`is_staff=True`)
- Non-staff users are redirected back to the dashboard home
- Unauthenticated users are redirected to the login page

## What It Shows

The page renders the taxonomy by:

- branch
- tier
- unit

For each unit, it displays:

- unit number
- title
- `feat`
- tags
- analysis families present on the unit
- `new` values for each analysis family
- `cumulative` values for each analysis family

This makes it easier to inspect the current curriculum structure without opening raw JSON files.

## Implementation

Files added for this debug page:

- [apps/dashboard/views/taxonomy.py](/Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/dashboard/views/taxonomy.py)
- [apps/dashboard/templates/dashboard/taxonomy_debug.html](/Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/dashboard/templates/dashboard/taxonomy_debug.html)
- [apps/dashboard/tests/test_taxonomy_debug_view.py](/Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/dashboard/tests/test_taxonomy_debug_view.py)

Routing entry:

- [apps/dashboard/urls.py](/Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/dashboard/urls.py)

## Notes

- This page is read-only.
- It does not edit the taxonomy.
- It is meant for debugging and curriculum review, not student-facing use.
- The page currently uses `music_theory_taxonomy_with_branches.json` rather than `music_theory_taxonomy.json`, because the branched file is the more complete curriculum view for inspection.
