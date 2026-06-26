#!/usr/bin/env bash
# Runs every Node test in the repo and exits non-zero if any fail.
# Three roots: production-source tests, integration tests, and theory goldens.
# IMPORTANT: theory_golden/ MUST be included or the new JS parity/e2e gates
# silently never run.
set -u

ROOTS=(
  "lab/static/js/src"
  "lab/static/js/test"
  "theory_golden"
)

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_root"

failed=0
found=0

while IFS= read -r -d '' test_file; do
  found=$((found + 1))
  echo "=== node $test_file ==="
  if ! node "$test_file"; then
    failed=$((failed + 1))
    echo "FAILED: $test_file"
  fi
done < <(find "${ROOTS[@]}" -name '*.test.js' -print0 2>/dev/null | sort -z)

echo ""
echo "Ran $found JS test file(s); $failed failed."
if [ "$failed" -gt 0 ]; then
  exit 1
fi
