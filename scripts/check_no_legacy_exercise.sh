#!/bin/bash
# scripts/check_no_legacy_exercise.sh
# CI guardrail to prevent regression into legacy exercise schemas.

set -e

echo "Checking database for non-UMTO compliant exercises..."

# Query count of exercises missing the isUMTO flag.
# We use -v 0 to suppress Django management command noise.
NON_UMTO_COUNT=$(python manage.py shell -v 0 -c "
from apps.exercises.models import Exercise
legacy_count = 0
try:
    for ex in Exercise.objects.only('data').iterator():
        if not (isinstance(ex.data, dict) and ex.data.get('isUMTO')):
            legacy_count += 1
    print(legacy_count)
except Exception as e:
    import sys
    sys.stderr.write(str(e) + '\n')
    sys.exit(1)
" | tail -n 1)

# Ensure NON_UMTO_COUNT is a number
if ! [[ "$NON_UMTO_COUNT" =~ ^[0-9]+$ ]]; then
  echo "ERROR: Failed to parse non-UMTO count. Received: '$NON_UMTO_COUNT'"
  exit 1
fi

if [ "$NON_UMTO_COUNT" -gt 0 ]; then
  echo "--------------------------------------------------------"
  echo "FAILED: Found $NON_UMTO_COUNT exercises with legacy schema."
  echo "All exercises must now follow the Universal Music Theory Object (UMTO) standard."
  echo "Please migrate legacy data using 'migrate_unit1_to_umto' or use the umto_factory."
  echo "--------------------------------------------------------"
  exit 1
else
  echo "--------------------------------------------------------"
  echo "SUCCESS: All exercises are UMTO compliant ($NON_UMTO_COUNT)."
  echo "--------------------------------------------------------"
  exit 0
fi
