#!/bin/bash
# Fails if any production source file contains a legacy Exercise type string.
# Test fixtures and legacy migration tests are allowed.

set -euo pipefail

BAD=$(grep -rlE '"type":\s*"chorale(_identification)?"' \
  apps/ lab/ \
  --include='*.py' --include='*.js' --include='*.html' \
  --exclude-dir='fixtures' \
  --exclude-dir='legacy_fixtures' \
  --exclude-dir='__pycache__' \
  --exclude='test_migrate_unit1_to_umto.py' \
  --exclude='umto_test_helpers.py' \
  || true)

if [ -n "$BAD" ]; then
  echo "ERROR: Legacy Exercise type strings found in:"
  echo "$BAD"
  echo
  echo "All new Exercise creation must use apps.exercises.umto_factory."
  echo "See CLAUDE.md 'UMTO is the Canonical Exercise Representation'."
  exit 1
fi
echo "OK: no legacy Exercise type strings in production source."
