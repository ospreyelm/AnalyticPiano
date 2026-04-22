# Unit 1 Meaningful Curriculum With MIDI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a student-meaningful Unit 1 curriculum with capped playlists, full skill coverage, and both identification and MIDI play tracks.

**Architecture:** Keep the existing student flow and mastery engine, but replace oversized static pools with curated capped playlists per skill lane. Extend the Unit 1 generator to produce two parallel tracks (identify and matching) while emitting payloads that match the existing frontend `matching` schema (no new frontend exercise type work). Preserve current student-facing Unit 1 labels (`clefs`, `enharmonic`) and bridge them to canonical mastery tags in progress aggregation.

**Tech Stack:** Django, PostgreSQL, management commands, existing RequireJS frontend exercise runtime, Django tests.

---

## Scope and decomposition

This plan intentionally covers one subsystem: Unit 1 curriculum generation and student consumption. It is implemented in six bounded tasks so each task yields testable progress and can be merged independently.

## File map

### Existing files to modify
- `apps/exercises/management/commands/generate_unit1.py`
  - Add configurable caps and lane presets.
  - Generate both `chorale_identification` and `matching` exercises.
  - Create multiple curated playlists by skill lane.
- `apps/exercises/tests/test_generate_unit1.py`
  - Add tests for cap behavior, lane tagging, and matching payload shape.
- `apps/student/views.py`
    - Keep current Unit 1 display tags and lane display ordering.
- `apps/student/progress.py`
    - Add required compatibility mapper so legacy Unit 1 labels aggregate canonical mastery tags.
- `docs/unit_1_note_reading_strategy.md`
  - Update curriculum shape and playlist count targets.

### New files to create
- `apps/student/tests/test_unit1_curriculum_integration.py`
  - Validate Unit 1 student page links and lane visibility for all target skills.
- `apps/exercises/management/commands/rebuild_unit1_playlists.py`
  - Safe command to regenerate Unit 1 playlists from existing generated exercises without reimporting corpus.

---

### Task 1: Lock down curriculum and cap rules in tests first

**Files:**
- Modify: `apps/exercises/tests/test_generate_unit1.py`
- Create: `apps/student/tests/test_unit1_curriculum_integration.py`
- Test: `apps/exercises/tests/test_generate_unit1.py`, `apps/student/tests/test_unit1_curriculum_integration.py`

- [ ] **Step 1: Write failing tests for playlist cap limits**

```python
# apps/exercises/tests/test_generate_unit1.py

def test_generate_unit1_enforces_playlist_cap(self):
    call_command(
        "generate_unit1",
        author=self.author.email,
        input_dir=self.test_dir,
        clef="both",
        max_per_playlist=12,
    )
    treble = Playlist.objects.get(name="Unit 1 - Note Names (Treble)")
    bass = Playlist.objects.get(name="Unit 1 - Note Names (Bass)")
    self.assertLessEqual(treble.exerciseplaylistordered_set.count(), 12)
    self.assertLessEqual(bass.exerciseplaylistordered_set.count(), 12)
```

- [ ] **Step 2: Write failing tests for matching lane generation**

```python
# apps/exercises/tests/test_generate_unit1.py

def test_generate_unit1_creates_matching_lane_exercises(self):
    call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")
    ex = Exercise.objects.filter(description__icontains="(matching)").first()
    self.assertIsNotNone(ex)
    self.assertEqual(ex.data.get("type"), "matching")
    self.assertIn("analysis", ex.data)
    self.assertIn("chord", ex.data)
    self.assertIsInstance(ex.data["chord"], list)
    self.assertIn("visible", ex.data["chord"][0])
    self.assertIn("hidden", ex.data["chord"][0])
    self.assertIn("rhythmValue", ex.data["chord"][0])
```

- [ ] **Step 3: Write failing student integration tests for Unit 1 lane coverage**

```python
# apps/student/tests/test_unit1_curriculum_integration.py

def test_unit1_page_shows_all_skill_lanes(self):
    response = self.client.get(reverse("student:unit", kwargs={"unit_num": 1}))
    self.assertContains(response, "Note Names")
    self.assertContains(response, "Ledger Lines")
    self.assertContains(response, "Clefs")
    self.assertContains(response, "Enharmonics")
```

- [ ] **Step 4: Run tests and verify RED**

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit1 apps.student.tests.test_unit1_curriculum_integration -v 2`

Expected:
- New tests fail because `max_per_playlist`, matching lane generation, and full skill lane wiring are not implemented.

- [ ] **Step 5: Commit failing tests**

```bash
git add apps/exercises/tests/test_generate_unit1.py apps/student/tests/test_unit1_curriculum_integration.py
git commit -m "test: define Unit 1 caps, matching lane, and skill-lane expectations"
```

---

### Task 2: Add cap controls and lane presets to Unit 1 generator

**Files:**
- Modify: `apps/exercises/management/commands/generate_unit1.py`
- Test: `apps/exercises/tests/test_generate_unit1.py`

- [ ] **Step 1: Add CLI args for capping and lane selection**

```python
# add_arguments()
parser.add_argument("--max-per-playlist", type=int, default=36)
parser.add_argument("--max-per-stage", type=int, default=12)
parser.add_argument("--lanes", choices=["identify", "matching", "both"], default="both")
```

- [ ] **Step 2: Implement capped selection after stage interleave**

```python
import re

STAGE_RE = re.compile(r"Stage\s+(\d+)\s*$")

def _extract_stage_from_description(description):
    m = STAGE_RE.search(description or "")
    if not m:
        raise ValueError(f"Cannot parse stage from description: {description}")
    return int(m.group(1))
```

```python
# after ordered = _weighted_interleave(...)
if max_per_stage > 0:
    stage_counts = defaultdict(int)
    filtered = []
    for ex in ordered:
        stage_num = _extract_stage_from_description(ex.description)
        if stage_counts[stage_num] >= max_per_stage:
            continue
        filtered.append(ex)
        stage_counts[stage_num] += 1
    ordered = filtered

if max_per_playlist > 0:
    ordered = ordered[:max_per_playlist]
```

- [ ] **Step 3: Ensure deterministic course playlist order assignment**

```python
# before creating PlaylistCourseOrdered row
existing = PlaylistCourseOrdered.objects.filter(course=course).order_by("order", "_id")
if not existing.filter(playlist=playlist).exists():
    next_order = (existing.last().order + 1) if existing.exists() else 1
    PlaylistCourseOrdered.objects.create(course=course, playlist=playlist, order=next_order)
```

- [ ] **Step 4: Re-run tests and verify GREEN for cap tests**

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit1::GenerateUnit1Tests::test_generate_unit1_enforces_playlist_cap -v 2`

Expected:
- PASS.

- [ ] **Step 5: Commit cap implementation**

```bash
git add apps/exercises/management/commands/generate_unit1.py
git commit -m "feat: add Unit 1 playlist and stage cap controls"
```

---

### Task 3: Generate matching track alongside identification track

**Files:**
- Modify: `apps/exercises/management/commands/generate_unit1.py`
- Test: `apps/exercises/tests/test_generate_unit1.py`

- [ ] **Step 1: Build matching payload function and use existing voice-window extraction**

```python
def _build_matching_payload(chord_rows, key_name, intro_text):
    return {
        "type": "matching",
        "staffDistribution": "keyboard",
        "key": f"j{key_name}_" if len(key_name) == 1 else "jC_",
        "analysis": {
            "enabled": True,
            "mode": {
                "note_names": True,
                "solfege": False,
                "scale_degrees": False,
            },
        },
        "chord": chord_rows,
        "introText": intro_text,
        "reviewText": "Great work.",
    }

def _midi(step, octave, alter=0):
    semitones = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return ((octave + 1) * 12) + semitones[step] + int(alter)

def _voice_window_to_matching_chords(one_voice_score):
    rows = []
    for measure in one_voice_score.get("measures", []):
        for staff in measure.get("staves", {}).values():
            for voice in staff.get("voices", []):
                for item in voice.get("items", []):
                    if item.get("kind") != "note":
                        continue
                    p = item.get("pitch", {})
                    midi = _midi(p["step"], p["octave"], p.get("alter", 0))
                    rows.append({
                        "visible": [midi],
                        "hidden": [],
                        "rhythmValue": item.get("duration", {}).get("type", "q"),
                    })
    return rows
```

- [ ] **Step 2: Create identify/matching exercise variants based on lane flag**

```python
if lanes in ("identify", "both"):
    create_identification_exercise(...)
if lanes in ("matching", "both"):
    chord_rows = _voice_window_to_matching_chords(one_voice)
    create_matching_exercise(chord_rows=chord_rows, ...)
```

- [ ] **Step 3: Prefix descriptions and playlist names by lane and mode**

```python
desc = f"{bwv.upper()} mm.{human_start}-{human_end} - {voice_name.title()} (matching) Stage {stage}"
playlist_name = "Unit 1 - Note Names (Treble Play)"
```

- [ ] **Step 4: Verify matching payload parses in existing runtime contract**

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py shell -c "from apps.exercises.models import Exercise; ex=Exercise.objects.filter(description__icontains='(matching)').first(); print(ex.data['type'], bool(ex.data.get('chord')), ex.data['chord'][0].keys())"`

Expected:
- Output includes `matching True dict_keys(['visible', 'hidden', 'rhythmValue'])`.

- [ ] **Step 5: Run matching-lane tests and verify GREEN**

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit1::GenerateUnit1Tests::test_generate_unit1_creates_matching_lane_exercises -v 2`

Expected:
- PASS.

- [ ] **Step 6: Commit matching lane implementation**

```bash
git add apps/exercises/management/commands/generate_unit1.py
git commit -m "feat: generate Unit 1 matching lane alongside identification"
```

---

### Task 4: Expand Unit 1 skill lane coverage and student tag compatibility

**Files:**
- Modify: `apps/student/views.py`
- Modify: `apps/student/progress.py`
- Modify: `apps/exercises/management/commands/generate_unit1.py`
- Test: `apps/student/tests/test_unit1_curriculum_integration.py`

- [ ] **Step 1: Define canonical Unit 1 skill tags for student progress**

```python
# apps/student/views.py
UNIT_1_TAGS = [
    "Note_Names",
    "Ledger_Lines",
    "clefs",
    "enharmonic",
]

skill_display_names = {
    "Note_Names": "Note Names",
    "Ledger_Lines": "Ledger Lines",
    "clefs": "Clefs (Treble & Bass)",
    "enharmonic": "Enharmonics",
}
```

- [ ] **Step 2: Add backward-compatible mapping for existing legacy tags**

```python
# apps/student/progress.py
TAG_ALIASES = {
    "clefs": ["Read_Treble_Clef", "Read_Bass_Clef", "clefs"],
    "enharmonic": ["Enharmonic_Reading", "enharmonic"],
    "Note_Names": ["Note_Names"],
    "Ledger_Lines": ["Ledger_Lines"],
}

def get_unit_progress(user, skill_tags):
    expanded = set()
    for tag in skill_tags:
        expanded.update(TAG_ALIASES.get(tag, [tag]))
    mastery_rows = StudentSkillMastery.objects.filter(user=user, skill_tag__in=expanded)
    mastery_map = {m.skill_tag: m.level for m in mastery_rows}

    def best_level(tags_for_skill):
        levels = [mastery_map.get(t, StudentSkillMastery.LEVEL_NOT_STARTED) for t in tags_for_skill]
        order = StudentSkillMastery.LEVEL_CHOICES
        idx = {k: i for i, (k, _) in enumerate(order)}
        return max(levels, key=lambda lv: idx[lv])

    # compute per requested skill tag using alias bundles
    ...
```

- [ ] **Step 3: Update generator lane metadata to include these tags**

```python
LANE_TAGS = {
    "note_names_treble": ["unit:1", "Note_Names", "Read_Treble_Clef"],
    "note_names_bass": ["unit:1", "Note_Names", "Read_Bass_Clef"],
    "ledger_lines": ["unit:1", "Ledger_Lines"],
    "clefs_treble": ["unit:1", "clefs", "Read_Treble_Clef"],
    "clefs_bass": ["unit:1", "clefs", "Read_Bass_Clef"],
    "enharmonic": ["unit:1", "enharmonic", "Enharmonic_Reading"],
}
```

- [ ] **Step 4: Run student integration tests and verify GREEN**

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.student.tests.test_unit1_curriculum_integration -v 2`

Expected:
- PASS.

- [ ] **Step 5: Commit student/tag alignment**

```bash
git add apps/student/views.py apps/student/progress.py apps/exercises/management/commands/generate_unit1.py apps/student/tests/test_unit1_curriculum_integration.py
git commit -m "feat: align Unit 1 student skills with mastery-aware tags"
```

---

### Task 5: Add regeneration command for safe playlist rebuilding

**Files:**
- Create: `apps/exercises/management/commands/rebuild_unit1_playlists.py`
- Test: `apps/exercises/tests/test_generate_unit1.py`

- [ ] **Step 1: Write failing test for rebuild command idempotency**

```python
def test_rebuild_unit1_playlists_is_idempotent(self):
    def snapshot():
        out = {}
        for p in Playlist.objects.filter(name__icontains="Unit 1").order_by("name"):
            rows = p.exerciseplaylistordered_set.order_by("order").values_list("exercise__id", flat=True)
            out[p.name] = list(rows)
        return out

    call_command("rebuild_unit1_playlists", author=self.author.email)
    first = snapshot()
    call_command("rebuild_unit1_playlists", author=self.author.email)
    second = snapshot()
    self.assertEqual(first, second)
```

- [ ] **Step 2: Implement command to rebuild ordered rows from existing tagged exercises**

```python
# rebuild_unit1_playlists.py
LANE_PLAYLISTS = {
    "Note_Names": "Unit 1 - Note Names (Treble)",
    "clefs": "Unit 1 - Clefs",
    "Ledger_Lines": "Unit 1 - Ledger Lines",
    "enharmonic": "Unit 1 - Enharmonics",
}

for lane_tag, playlist_name in LANE_PLAYLISTS.items():
    playlist = Playlist.objects.get(name=playlist_name, authored_by=author)
    rows = (
        Exercise.objects.filter(skill_tags__contains=["unit:1"])
        .filter(skill_tags__contains=[lane_tag])
        .order_by("complexity", "description")
    )
    ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
    for idx, ex in enumerate(rows, start=1):
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=ex, order=idx)
```

- [ ] **Step 3: Run rebuild tests and verify GREEN**

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit1 -v 2`

Expected:
- PASS.

- [ ] **Step 4: Commit rebuild command**

```bash
git add apps/exercises/management/commands/rebuild_unit1_playlists.py apps/exercises/tests/test_generate_unit1.py
git commit -m "feat: add safe Unit 1 playlist rebuild command"
```

---

### Task 6: Documentation and rollout verification

**Files:**
- Modify: `docs/unit_1_note_reading_strategy.md`
- Modify: `docs/superpowers/specs/2026-04-20-student-app-design.md`

- [ ] **Step 1: Update docs with final lane matrix and target caps**

```markdown
Per-playlist cap: 36 default, 48 hard max.
Unit 1 playlists include identification and matching tracks.
```

- [ ] **Step 2: Run final end-to-end verification commands**

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test apps.exercises.tests.test_generate_unit1 apps.student.tests.test_views apps.student.tests.test_unit1_curriculum_integration -v 2`

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py generate_unit1 --author <email> --clef both --lanes both --max-per-playlist 36 --max-per-stage 12`

Run:
`DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py shell -c "from apps.exercises.models import Playlist; print([(p.name, p.exerciseplaylistordered_set.count()) for p in Playlist.objects.filter(skill_tags__contains=['unit:1'])])"`

Expected:
- All tests pass.
- Unit 1 playlists exist for all intended lanes.
- No playlist exceeds configured cap.

- [ ] **Step 3: Commit docs and verification updates**

```bash
git add docs/unit_1_note_reading_strategy.md docs/superpowers/specs/2026-04-20-student-app-design.md
git commit -m "docs: document capped Unit 1 dual-lane curriculum rollout"
```

---

## Rollout checklist

- [ ] Back up existing Unit 1 playlists.
- [ ] Run `rebuild_unit1_playlists` in staging.
- [ ] Verify student `/s/units/1/` displays all lanes.
- [ ] Verify first exercise load time under 1 second for each lane.
- [ ] Promote to production.

## Risks and mitigations

1. Risk: Legacy tags (`clefs`, `enharmonic`) not reflected in mastery.
- Mitigation: keep legacy UnitView tags and map them to canonical mastery tags in `get_unit_progress`.

2. Risk: Matching payload from voice windows may differ from existing authored matching schema.
- Mitigation: generate `matching` payload with existing `chord` rows and assert runtime-required keys in tests.

4. Risk: `PlaylistCourseOrdered` rows all receive `order=1`, causing undefined Unit 1 sequence.
- Mitigation: assign next available order when linking each playlist to course.

3. Risk: Playlist cap too aggressive for some instructors.
- Mitigation: expose cap args on command and document defaults.

## Plan self-review

1. Spec coverage check: covers playlist size control, full Unit 1 skill lanes, MIDI matching inclusion, and student progress alignment.
2. Placeholder scan: no TODO/TBD placeholders remain in task steps.
3. Type consistency: `max_per_playlist`, `max_per_stage`, and `lanes` names are consistent across tests and implementation steps.
