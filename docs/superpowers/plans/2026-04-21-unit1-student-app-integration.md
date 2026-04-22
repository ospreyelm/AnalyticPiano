# Unit 1 Student App Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing Unit 1 note-name exercises (created by `generate_unit1`) into the student app so students can navigate through them, submit answers, and see mastery progress update.

**Architecture:** Four gaps to close: (1) `PlayerView` needs to find the `Course` linked to the playlist and pass it so `IdentificationAttempt` saves correctly; (2) next/prev exercise navigation must route back to the student player, not the instructor lab; (3) the Unit page must surface both Treble and Bass playlists; (4) after the last exercise the player should return the student to the unit page rather than 404.

**Tech Stack:** Django 4.x, Python 3.11+, pytest-django, existing `generate_exercise_context` in `lab/views.py`

---

## File Map

| File | What changes |
|------|-------------|
| `apps/student/views.py` | `PlayerView`: look up course from playlist; pass exercise_num from query param; override next/prev URLs to stay in student player |
| `apps/student/urls.py` | Add `exercise_num` path param to player URL |
| `apps/student/views.py` | `UnitView`: surface both Treble and Bass playlists per skill |
| `apps/student/templates/student/unit.html` | Show separate Practice Treble / Practice Bass links |
| `apps/student/tests/test_views.py` | Tests for each fix |

---

## Task 1: Look Up Course in PlayerView + Pass exercise_num

**Problem:** `PlayerView` calls `generate_exercise_context(..., course=None)`. The JS player posts `IdentificationAttempt` with `course_ID` from the context — if it's `None`, `apps/exercises/views.py:136` does `Course.objects.get(id=None)` and returns 400. Also, `exercise_num` is hardcoded to `1` — deep-links and resume don't work.

**Files:**
- Modify: `apps/student/urls.py`
- Modify: `apps/student/views.py` — `PlayerView.get`
- Modify: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Add to `apps/student/tests/test_views.py`:

```python
from apps.exercises.models import Exercise, Playlist, ExercisePlaylistOrdered, Course, PlaylistCourseOrdered

@pytest.fixture
def unit1_setup(db):
    """Minimal playlist+course wired the same way generate_unit1 does it."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    author = User.objects.create_user(email="author@test.com", password="x", is_staff=True)

    ex = Exercise.objects.create(
        description="BWV10.7 mm.1-2 - Soprano (note_name) Stage 1",
        data={"type": "chorale_identification", "analysisType": "note_name", "score": {"meta": {"key": "G", "time": "4/4"}, "measures": []}},
        authored_by=author,
        is_public=True,
        skill_tags=["unit:1", "Note_Names"],
    )
    pl = Playlist.objects.create(
        name="Unit 1 - Note Names (Treble)",
        authored_by=author,
        is_public=True,
        skill_tags=["unit:1", "Note_Names"],
        tags=["unit:1", "Note_Names"],
    )
    ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex, order=1)
    course = Course.objects.create(
        title="Unit 1: Pitch & Staff Notation",
        authored_by=author,
        is_public=True,
    )
    PlaylistCourseOrdered.objects.create(playlist=pl, course=course, order=1)
    return {"playlist": pl, "exercise": ex, "course": course}


def test_player_returns_200_with_exercise_num(client, student, unit1_setup):
    client.force_login(student)
    pl = unit1_setup["playlist"]
    url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={pl.id}&exercise_num=1"
    response = client.get(url)
    assert response.status_code == 200


def test_player_context_has_course_id(client, student, unit1_setup):
    """Exercise context must include courseId so IdentificationAttempt saves."""
    client.force_login(student)
    pl = unit1_setup["playlist"]
    url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={pl.id}&exercise_num=1"
    response = client.get(url)
    assert response.status_code == 200
    # exercise_context is embedded in template via RequirejsContext — check rendered HTML
    assert unit1_setup["course"].id.encode() in response.content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest apps/student/tests/test_views.py::test_player_context_has_course_id -v
```

Expected: FAIL (course_id is None in current context → course ID not in response content)

- [ ] **Step 3: Fix PlayerView**

Replace `PlayerView.get` in `apps/student/views.py`:

```python
class PlayerView(View):
    @_require_student
    def get(self, request, unit_num):
        playlist_id = request.GET.get("playlist")
        if not playlist_id:
            raise Http404("Playlist ID is required.")

        playlist = get_object_or_404(Playlist, id=playlist_id)

        if "unit:1" not in (playlist.tags or []) and "unit:1" not in (playlist.skill_tags or []):
            raise Http404("Playlist not part of Unit 1.")

        exercise_num = int(request.GET.get("exercise_num", 1))

        # Look up course linked to this playlist (generate_unit1 always creates one)
        from apps.exercises.models import PlaylistCourseOrdered
        pco = PlaylistCourseOrdered.objects.filter(playlist=playlist).select_related("course").first()
        course = pco.course if pco else None

        exercise = playlist.get_exercise_obj_by_num(exercise_num)
        if not exercise:
            # Past end of playlist — send student back to unit page
            return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

        exercise_context = generate_exercise_context(
            exercise_num,
            exercise,
            request.user,
            playlist,
            course,
        )

        # Override next/prev URLs to stay in student player (not lab)
        base_url = reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={playlist_id}"
        total = playlist.exercise_count
        next_num = exercise_num + 1 if exercise_num < total else None
        prev_num = exercise_num - 1 if exercise_num > 1 else None
        exercise_context["nextExerciseUrl"] = (base_url + f"&exercise_num={next_num}") if next_num else None
        exercise_context["prevExerciseUrl"] = (base_url + f"&exercise_num={prev_num}") if prev_num else None

        rj_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)
        rj_context.set_app_module("app/components/app/exercise")
        rj_context.set_module_params("app/components/app/exercise", exercise_context)

        context = {
            "unit_num": unit_num,
            "playlist": playlist,
            "exercise_num": exercise_num,
            "total_exercises": total,
        }
        rj_context.add_to_view(context)

        return render(request, "student/player.html", context)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest apps/student/tests/test_views.py::test_player_returns_200_with_exercise_num apps/student/tests/test_views.py::test_player_context_has_course_id -v
```

Expected: both PASS

- [ ] **Step 5: Commit**

```bash
git add apps/student/views.py apps/student/tests/test_views.py
git commit -m "fix(student): PlayerView looks up course from playlist, respects exercise_num param"
```

---

## Task 2: Student-Side Next/Prev Navigation URL (verify end-to-end)

**Problem:** The exercise context's `nextExerciseUrl` and `prevExerciseUrl` were previously pointing to `lab:playlist-view` (instructor UI). Task 1 overrides them — this task verifies the override works and adds a test for the "past end" redirect.

**Files:**
- Modify: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write failing test for end-of-playlist redirect**

Add to `apps/student/tests/test_views.py`:

```python
def test_player_redirects_to_unit_when_exercise_num_exceeds_playlist(client, student, unit1_setup):
    """Requesting exercise_num beyond playlist length → redirect to unit page."""
    client.force_login(student)
    pl = unit1_setup["playlist"]
    url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={pl.id}&exercise_num=999"
    response = client.get(url)
    assert response.status_code == 302
    assert response["Location"] == reverse("student:unit", kwargs={"unit_num": 1})


def test_player_next_url_stays_in_student_player(client, student, unit1_setup):
    """nextExerciseUrl must point to student player, not lab."""
    client.force_login(student)
    pl = unit1_setup["playlist"]
    # Add a second exercise so next_num exists
    ex2 = Exercise.objects.create(
        description="BWV10.7 mm.2-3 - Soprano (note_name) Stage 1",
        data={"type": "chorale_identification", "analysisType": "note_name", "score": {"meta": {"key": "G", "time": "4/4"}, "measures": []}},
        authored_by=unit1_setup["playlist"].authored_by,
        is_public=True,
        skill_tags=["unit:1", "Note_Names"],
    )
    ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex2, order=2)

    url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={pl.id}&exercise_num=1"
    response = client.get(url)
    assert response.status_code == 200
    # nextExerciseUrl should reference student player path, not /lab/
    assert b"/s/units/" in response.content
    assert b"/lab/" not in response.content or b"nextExerciseUrl" not in response.content
```

- [ ] **Step 2: Run to verify first test fails (second may pass already)**

```bash
python -m pytest apps/student/tests/test_views.py::test_player_redirects_to_unit_when_exercise_num_exceeds_playlist apps/student/tests/test_views.py::test_player_next_url_stays_in_student_player -v
```

- [ ] **Step 3: Confirm Task 1 code already satisfies both** 

The `PlayerView` from Task 1 already redirects when `exercise = None` and overrides next/prev URLs. If tests pass without changes, proceed. If the "next URL in lab" test fails because `generate_exercise_context` still writes `lab:playlist-view` URLs into another key, audit `exercise_context` keys in `lab/views.py:generate_exercise_context` and override any additional URL keys:

```python
# After the two overrides already set in Task 1, also clear the exercise-level URLs
# that generate_exercise_context may have set using the lab route
exercise_context["nextExerciseUrl"] = (base_url + f"&exercise_num={next_num}") if next_num else None
exercise_context["prevExerciseUrl"] = (base_url + f"&exercise_num={prev_num}") if prev_num else None
# Some JS reads "nextExercise" (without Url suffix) — clear those too if present
exercise_context.pop("nextExercise", None)
exercise_context.pop("prevExercise", None)
```

- [ ] **Step 4: Run full student test suite**

```bash
python -m pytest apps/student/tests/ -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add apps/student/tests/test_views.py apps/student/views.py
git commit -m "test(student): verify end-of-playlist redirect and next/prev stay in student player"
```

---

## Task 3: Surface Both Treble and Bass Playlists on Unit Page

**Problem:** `UnitView` calls `_get_playlist_id_for_tag("Note_Names")` which returns only one playlist. `generate_unit1` creates two: `"Unit 1 - Note Names (Treble)"` and `"Unit 1 - Note Names (Bass)"`. The unit page shows a single "Practice" button; students can't choose clef.

**Files:**
- Modify: `apps/student/views.py` — `_get_playlist_id_for_tag` → `_get_playlists_for_tag`; `UnitView`
- Modify: `apps/student/templates/student/unit.html`
- Modify: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Add to `apps/student/tests/test_views.py`:

```python
def test_unit_page_shows_both_treble_and_bass_playlist_links(client, student, unit1_setup, db):
    """Unit page must link to both treble and bass playlists when both exist."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    author = User.objects.get(email="author@test.com")

    ex_bass = Exercise.objects.create(
        description="BWV10.7 mm.1-2 - Bass (note_name) Stage 1",
        data={"type": "chorale_identification", "analysisType": "note_name", "score": {"meta": {"key": "G", "time": "4/4"}, "measures": []}},
        authored_by=author,
        is_public=True,
        skill_tags=["unit:1", "Note_Names"],
    )
    pl_bass = Playlist.objects.create(
        name="Unit 1 - Note Names (Bass)",
        authored_by=author,
        is_public=True,
        skill_tags=["unit:1", "Note_Names"],
        tags=["unit:1", "Note_Names"],
    )
    ExercisePlaylistOrdered.objects.create(playlist=pl_bass, exercise=ex_bass, order=1)
    PlaylistCourseOrdered.objects.create(playlist=pl_bass, course=unit1_setup["course"], order=2)

    client.force_login(student)
    url = reverse("student:unit", kwargs={"unit_num": 1})
    response = client.get(url)
    assert response.status_code == 200
    # Both playlist IDs must appear in the response
    assert unit1_setup["playlist"].id.encode() in response.content
    assert pl_bass.id.encode() in response.content
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest apps/student/tests/test_views.py::test_unit_page_shows_both_treble_and_bass_playlist_links -v
```

Expected: FAIL (only one playlist link rendered)

- [ ] **Step 3: Replace `_get_playlist_id_for_tag` with `_get_playlists_for_tag` in `views.py`**

```python
def _get_playlists_for_tag(tag: str) -> list[dict]:
    """Return list of {id, name} for all Unit 1 playlists matching tag, ordered by name."""
    playlists = (
        Playlist.objects.filter(skill_tags__contains=["unit:1"])
        .filter(skill_tags__contains=[tag])
        .order_by("name")
        .values("id", "name")
    )
    return list(playlists)
```

Also remove the old `_get_playlist_id_for_tag` function entirely (it's only called from `HomeView` and `UnitView` — both will be updated).

- [ ] **Step 4: Update `UnitView` to use new helper**

Replace the skill-building loop inside `UnitView.get`:

```python
skills = []
for s in progress["skills"]:
    tag = s["tag"]
    playlists_for_tag = _get_playlists_for_tag(tag)
    playlist_links = [
        {
            "id": pl["id"],
            "name": pl["name"],
            "url": reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={pl['id']}&exercise_num=1",
        }
        for pl in playlists_for_tag
    ]
    skills.append({
        "tag": tag,
        "name": skill_display_names.get(tag, tag),
        "level": s["level"],
        "playlist_links": playlist_links,
    })
```

- [ ] **Step 5: Update `HomeView` to use new helper for resume URL**

In `HomeView.get`, replace the `_get_playlist_id_for_tag` call:

```python
resume_url = None
if unit1_progress["resume_tag"]:
    playlists = _get_playlists_for_tag(unit1_progress["resume_tag"])
    if playlists:
        # Default resume to the first playlist (treble) — student can navigate to bass from unit page
        resume_playlist_id = playlists[0]["id"]
        resume_url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={resume_playlist_id}&exercise_num=1"
```

- [ ] **Step 6: Update `unit.html` template**

Replace the skill row's single Practice button:

```html
{% for skill in skills %}
  <div class="s-skill-row {% if skill.level == 'mastered' %}mastered{% elif skill.level != 'not_started' %}in-progress{% endif %}">
    <div class="s-skill-dot {{ skill.level }}">
      {% if skill.level == 'mastered' %}✓{% elif skill.level != 'not_started' %}●{% endif %}
    </div>
    <div class="s-skill-info">
      <div class="s-skill-name">{{ skill.name }}</div>
      <div class="s-skill-level {{ skill.level }}">
        {% if skill.level == 'mastered' %}Mastered
        {% elif skill.level != 'not_started' %}In Progress
        {% else %}Not Started{% endif %}
      </div>
    </div>
    <div class="s-skill-actions">
      {% for link in skill.playlist_links %}
        <a href="{{ link.url }}" class="s-btn-secondary">{{ link.name }}</a>
      {% empty %}
        <span class="s-btn-secondary" style="opacity:0.4;cursor:default">Coming soon</span>
      {% endfor %}
    </div>
  </div>
{% endfor %}
```

- [ ] **Step 7: Run test**

```bash
python -m pytest apps/student/tests/test_views.py::test_unit_page_shows_both_treble_and_bass_playlist_links -v
```

Expected: PASS

- [ ] **Step 8: Run full student suite**

```bash
python -m pytest apps/student/tests/ -v
```

Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add apps/student/views.py apps/student/templates/student/unit.html apps/student/tests/test_views.py
git commit -m "feat(student): surface treble+bass playlists on unit page, fix resume URL"
```

---

## Task 4: Fix Playlist Tag Lookup (skill_tags vs tags)

**Problem:** `_get_playlists_for_tag` (Task 3) filters `skill_tags__contains=["unit:1"]`. But `generate_unit1` sets **both** `tags=["unit:1", "Note_Names"]` and `skill_tags=["unit:1", "Note_Names"]` on the playlist — so this works. However the old `seed_unit1_content` command sets only `tags`, not `skill_tags`. Both fields need to be checked to avoid regressions.

**Files:**
- Modify: `apps/student/views.py` — `_get_playlists_for_tag` to query both fields
- Modify: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Add to `apps/student/tests/test_views.py`:

```python
def test_get_playlists_for_tag_finds_playlist_with_only_tags_field(db):
    """Playlist with tag only in .tags (not .skill_tags) must still be found."""
    from django.contrib.auth import get_user_model
    from apps.student.views import _get_playlists_for_tag
    User = get_user_model()
    author = User.objects.create_user(email="tagonly@test.com", password="x", is_staff=True)
    pl = Playlist.objects.create(
        name="Unit 1 - Tags Only",
        authored_by=author,
        is_public=True,
        skill_tags=[],          # empty skill_tags
        tags=["unit:1", "Note_Names"],
    )
    results = _get_playlists_for_tag("Note_Names")
    ids = [r["id"] for r in results]
    assert pl.id in ids
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest apps/student/tests/test_views.py::test_get_playlists_for_tag_finds_playlist_with_only_tags_field -v
```

Expected: FAIL

- [ ] **Step 3: Update `_get_playlists_for_tag` to union both fields**

```python
from django.db.models import Q

def _get_playlists_for_tag(tag: str) -> list[dict]:
    """Return {id, name} for all Unit 1 playlists matching tag (checks both tags and skill_tags fields)."""
    q = (
        Q(skill_tags__contains=["unit:1"]) | Q(tags__contains=["unit:1"])
    ) & (
        Q(skill_tags__contains=[tag]) | Q(tags__contains=[tag])
    )
    playlists = Playlist.objects.filter(q).order_by("name").values("id", "name")
    return list(playlists)
```

- [ ] **Step 4: Run test**

```bash
python -m pytest apps/student/tests/test_views.py::test_get_playlists_for_tag_finds_playlist_with_only_tags_field -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest apps/student/tests/ -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add apps/student/views.py apps/student/tests/test_views.py
git commit -m "fix(student): playlist lookup checks both tags and skill_tags fields"
```

---

## Task 5: Smoke Test — Run generate_unit1 Dry Run + Verify Data Shape

**Goal:** Confirm `generate_unit1` output matches what the student app now expects. This is a manual verification step, not automated.

**Files:** None (read-only verification)

- [ ] **Step 1: Run dry-run**

```bash
python manage.py generate_unit1 --author=avnerdorman@gmail.com --dry-run 2>&1 | tail -20
```

Expected output ends with: `Dry-run complete`

- [ ] **Step 2: Check generated playlists exist in DB (if prior real run was done)**

```bash
python manage.py shell -c "
from apps.exercises.models import Playlist, PlaylistCourseOrdered
pls = Playlist.objects.filter(skill_tags__contains=['Note_Names'])
for pl in pls:
    pco = PlaylistCourseOrdered.objects.filter(playlist=pl).first()
    course = pco.course if pco else None
    print(f'{pl.name} | tags={pl.tags} | skill_tags={pl.skill_tags} | course={course}')
"
```

Expected: two playlists (`Treble` and `Bass`), both with `tags` and `skill_tags` containing `unit:1` and `Note_Names`, both linked to a course.

- [ ] **Step 3: Spot-check one exercise**

```bash
python manage.py shell -c "
from apps.exercises.models import Exercise
ex = Exercise.objects.filter(skill_tags__contains=['Note_Names']).order_by('complexity').first()
if ex:
    print('desc:', ex.description)
    print('type:', ex.data.get('type'))
    print('analysisType:', ex.data.get('analysisType'))
    print('skill_tags:', ex.skill_tags)
    print('complexity:', ex.complexity)
    score = ex.data.get('score', {})
    print('measure count:', len(score.get('measures', [])))
"
```

Expected: `type=chorale_identification`, `analysisType=note_name`, `complexity` in 10-14 range (stage 1, 0-4 accidentals).

- [ ] **Step 4: Commit if no code changes needed**

If Step 2/3 reveal data shape issues (e.g. playlists missing `skill_tags`), fix `generate_unit1._wire_playlists_and_course` to set both `tags` and `skill_tags`, re-run, and commit.

---

## Self-Review Against Spec

**Coverage check:**

| Requirement | Task |
|---|---|
| `PlayerView` finds course from playlist | Task 1 |
| `exercise_num` from query param | Task 1 |
| End-of-playlist → redirect to unit page | Task 2 |
| next/prev stay in student player | Task 2 |
| Both Treble and Bass playlists surfaced | Task 3 |
| Resume URL defaults to first playlist | Task 3 |
| Mastery updates on submit | Already wired — `record_attempt` in `exercises/views.py` fires when `course_id` is present, which Task 1 fixes |
| Playlist lookup handles `tags` vs `skill_tags` | Task 4 |
| Data integrity verification | Task 5 |

**Gaps noted:**
- `IdentificationAttempt` save endpoint (`/api/identification/`) requires `course_ID` to be non-null. Task 1 fixes this by looking up the course. If `generate_unit1` creates the playlist without linking a course (e.g. if run before the `Course` exists), Task 5 will catch it.
- The player template shows `Exercise X of -` for total count — Task 1 passes `total_exercises` to context but the template needs to use `{{ total_exercises }}` instead of `-`. Check `apps/student/templates/student/player.html` line with `js-player-total` and update if needed (no test needed — visual only).
