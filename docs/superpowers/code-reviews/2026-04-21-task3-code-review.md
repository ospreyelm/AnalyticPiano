# Code Quality Review: Task 3 - Generate Matching Track

**Date:** 2026-04-21  
**Reviewer:** Code Quality Audit  
**Task:** Generate matching track alongside identification track (Task 3)  
**Files Reviewed:** `apps/exercises/management/commands/generate_unit1.py`

---

## Executive Summary

**VERDICT: ✅ APPROVED**

Task 3 implementation passes code quality review with **no blocking issues**. All three prior concerns have been addressed correctly:

1. ✅ **Key token parsing** — Robust, handles standard key naming and edge cases
2. ✅ **Dry-run symmetry** — Consistent across both lanes, correctly prevents persistence
3. ✅ **Matching payload update behavior** — Idempotent, safe on rerun with proper change detection

**Safe to proceed to Task 4.**

---

## Detailed Findings

### Concern 1: Key Token Parsing in Matching Payload ✅

**Location:** Lines 151–158 (`_build_matching_payload()`)

```python
def _build_matching_payload(chord_rows, key_name, intro_text):
    normalized_key = (key_name or "C").strip()
    key_root = normalized_key.split()[0] if normalized_key else "C"

    if key_root and key_root[0] in STEP_ORDER:
        accidental = key_root[1] if len(key_root) > 1 and key_root[1] in ("#", "b") else ""
        key_token = f"j{key_root[0]}{accidental}_"
    else:
        key_token = "jC_"
```

**Analysis:**

| Aspect | Status | Details |
|--------|--------|---------|
| **Null safety** | ✅ PASS | Defaults `key_name` to "C" if None; handles empty strings via `.strip()` |
| **Multi-word keys** | ✅ PASS | `.split()[0]` correctly extracts root from "C major", "G# major", etc. |
| **Accidental parsing** | ✅ PASS | Checks `len(key_root) > 1` before accessing `[1]`; validates char is `#` or `b` |
| **Step validation** | ✅ PASS | `key_root[0] in STEP_ORDER` ensures step is valid (C–G); uppercase assumption matches Bach corpus standard |
| **Token format** | ✅ PASS | Output format `j{STEP}{ACCIDENTAL}_` matches runtime contract (e.g., `jC_`, `jG#_`) |
| **Fallback handling** | ✅ PASS | Invalid keys safely default to `jC_` rather than failing |

**Test Coverage:**  
Test `test_generate_unit1_creates_matching_lane_exercises` verifies payload contains correct keys (pass with G major test data).

**Recommendation:** No changes needed. Code is defensive and handles edge cases.

---

### Concern 2: Dry-Run Symmetry and Lane Branching ✅

**Locations:**
- Identify lane: Lines 305–324
- Matching lane: Lines 326–355
- Return early: Line 357

#### Identify Lane Logic

```python
if lanes in ("identify", "both"):
    identify_desc = f"{bwv.upper()} mm.{human_start}-{human_end} - {voice_name.title()} (note_name) Stage {stage}"
    identify = Exercise.objects.filter(description=identify_desc).first()
    if identify is not None:
        # Update existing
        if identify.complexity != complexity:
            identify.complexity = complexity
            if not dry_run:
                identify.save()
        created.append((target, "identify", stage, complexity, identify))
    elif not dry_run:
        # Create new (only if not dry_run)
        identify = Exercise(...)
        identify.save()
        created.append((target, "identify", stage, complexity, identify))
```

**Analysis:**
- ✅ Existing exercises: Always appends (safe—fetched from DB)
- ✅ New exercises: Only appends + creates if `not dry_run`
- ✅ Dry-run path: Skips both creation and append for new exercises
- ✅ Update path: Updates object in-memory, only persists if `not dry_run`

#### Matching Lane Logic

```python
if lanes in ("matching", "both"):
    ...
    matching = Exercise.objects.filter(description=matching_desc).first()
    if matching is None:
        if not dry_run:
            matching = Exercise(...)
            matching.save()
            # matching remains None in dry_run mode
    else:
        # Update existing
        changed = False
        if matching.data != matching_payload:
            matching.data = matching_payload
            changed = True
        if matching.complexity != complexity:
            matching.complexity = complexity
            changed = True
        if changed and not dry_run:
            matching.save()

    if matching is not None:
        created.append((target, "matching", stage, complexity, matching))
```

**Analysis:**
- ✅ Existing exercises: Appends after potential in-memory update
- ✅ New exercises: Only created if `not dry_run` (stays None otherwise)
- ✅ Dry-run path: `if matching is not None` prevents appending undefined exercises
- ✅ Update path: Changes recorded in-memory; only persisted if `not dry_run`

#### Return and Playlist Wiring

```python
if dry_run:
    self.stdout.write("Dry-run complete")
    return  # <-- Critical: exits before _wire_playlists_and_course()

self._wire_playlists_and_course(
    author,
    created,
    lanes=lanes,
    max_per_playlist=max_per_playlist,
    max_per_stage=max_per_stage,
)
```

**Analysis:**
- ✅ Early return prevents any playlist/course creation during dry-run
- ✅ Symmetry verified: Both lanes skip the same downstream operations
- ✅ No side effects in dry-run mode beyond initial query (safe)

**Verification:**
```
Exercise count before dry-run: 0
Dry-run complete
Exercise count after dry-run: 0
Generation complete. created=2
Exercise count after real run: 2
```
✅ Dry-run correctly prevented all persistence.

**Recommendation:** No changes needed. Both lanes are symmetric and correct.

---

### Concern 3: Matching Payload Update Behavior on Rerun ✅

**Location:** Lines 328–355

```python
matching = Exercise.objects.filter(description=matching_desc).first()
if matching is None:
    if not dry_run:
        matching = Exercise(
            description=matching_desc,
            data=matching_payload,
            authored_by=author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            complexity=complexity,
        )
        matching.save()
else:
    changed = False
    if matching.data != matching_payload:
        matching.data = matching_payload
        changed = True
    if matching.complexity != complexity:
        matching.complexity = complexity
        changed = True
    if changed and not dry_run:
        matching.save()
```

**Analysis:**

| Aspect | Status | Details |
|--------|--------|---------|
| **Idempotency** | ✅ PASS | Filters by `description` (unique identifier); handles create-or-update pattern |
| **Payload change detection** | ✅ PASS | `matching.data != matching_payload` correctly compares Django JSONField; detects full payload changes |
| **Complexity tracking** | ✅ PASS | Updates complexity separately; marked as changed only if it differs |
| **Minimal writes** | ✅ PASS | Only calls `.save()` if `changed=True`; avoids unnecessary DB hits |
| **Dry-run safety** | ✅ PASS | Changes recorded in-memory but not persisted if `dry_run=True` |
| **Chord data updates** | ✅ PASS | `_build_matching_payload()` is called each run, so chord rows are always fresh |

**Idempotency Test Results:**
```
First run: created=8
Second run (same input): created=8 (no new exercises, updates only)
```
✅ Idempotent.

**Rerun Scenario:**
If re-running with changed key signature:
1. Old matching exercise fetched from DB (line 329)
2. New payload built with updated key_token (line 337)
3. Payload comparison (line 348): `old != new` → `changed=True`
4. Updated and saved (line 352): `.save()`
✅ Correctly updates on payload change.

**Recommendation:** No changes needed. Idempotency is guaranteed by description-based lookup and change detection.

---

## Additional Quality Observations

### Strengths

1. **Consistent error handling** — Uses try/except for corpus loading; graceful fallbacks for missing fields
2. **Clear variable naming** — `human_start`, `human_end` make measure ranges explicit vs. 0-based indices
3. **Defensive pitch extraction** — Checks for required keys (`step`, `octave`) before accessing (line 161)
4. **Weighted interleaving** — Respects stage order via `STAGE_WEIGHTS` during playlist ordering
5. **Payload validation** — Tests verify full matching payload structure (keys, chord array, visibility)

### Minor Observations (Non-Blocking)

**Lines 305–306 (Identify description):**
```python
identify_desc = f"{bwv.upper()} mm.{human_start}-{human_end} - {voice_name.title()} (note_name) Stage {stage}"
```

Consider: The `(note_name)` label is only used for identify exercises. Matching exercises use `(matching)` (line 327). This is intentional and correct for lane distinction.

**Line 151 (Accidental range):**
The current implementation only supports `#` and `b` (no double accidentals). This matches the test data and Bach corpus scope. ✅ Acceptable.

---

## Security Review

| Check | Status | Details |
|-------|--------|---------|
| **SQL injection** | ✅ PASS | Uses ORM throughout; no raw SQL |
| **Path traversal** | ✅ PASS | Uses `os.path.join()` safely; no user input in paths |
| **JSON parsing** | ✅ PASS | Defensive chaining (`.get()` with defaults) prevents KeyError |
| **Field access** | ✅ PASS | No unsafe attribute access; validates pitch before using |

---

## Test Coverage

| Test | Purpose | Status |
|------|---------|--------|
| `test_generate_unit1_creates_matching_lane_exercises` | Verify payload structure | ✅ PASS |
| `test_generate_unit1_is_idempotent` | Verify rerun safety | ✅ PASS |
| `test_generate_unit1_enforces_playlist_cap` | Verify capping works | ✅ PASS (Task 2) |
| Dry-run manual test | Verify no persistence | ✅ PASS |

---

## Checklist for Task 4 Readiness

- [x] No blocking issues found
- [x] All three prior concerns addressed
- [x] Code passes existing tests
- [x] Dry-run behavior verified
- [x] Idempotency verified
- [x] No SQL injection / path traversal risks
- [x] Payload structure matches runtime contract
- [x] Lane branching is symmetric and correct

---

## Conclusion

Task 3 implementation is **production-ready**. The code correctly:

1. **Parses key tokens** with robust null and edge-case handling
2. **Maintains dry-run symmetry** across both lane branches
3. **Updates matching payloads** idempotently with proper change detection

**Approved to proceed with Task 4** (student tag compatibility and skill lane coverage).

---

**Signed off:** Code Quality Audit  
**Date:** 2026-04-21  
**Severity Level:** P0 (Production-Ready)
