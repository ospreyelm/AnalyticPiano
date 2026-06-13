# Phase 3E: Course Detail Replacement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent spec:** [docs/superpowers/plans/2026-06-13-phase3-curation-workbench.md](2026-06-13-phase3-curation-workbench.md)

**Prerequisite:** Plan 3C must be merged first (CSS for tabs must exist in `teacher.css`).

**Goal:** Replace the two legacy dashboard escape hatches in the course detail page (`dashboardEditUrl` and `dashboardActivityUrl`) with inline Settings and Activity tabs. Settings tab: edit course title and dates. Activity tab: read-only view of `course.performance_dict`. The `<details class="t-legacy-section">` block is deleted.

**Architecture:** `course_detail_view` in `apps/teacher/views.py` gains a `tab` query param and removes all `dashboard_*_url` construction. A new `course_settings_view` handles the settings POST. `course_detail.html` gains tab nav + two new tab panels. Activity panel renders from `window.__COURSE_DATA__.activity` (already present), not a new endpoint — no context mismatch.

**Critical fix (Codex review finding):** The original plan passed `pco_rows_json` (a JSON string) but the template needed `pco_rows_json_list` (a Python list). This plan passes `pco_rows` (a Python list used by both the existing Jinja-rendered timeline and the activity filter dropdown), fixing the mismatch cleanly.

**Tech Stack:** Django 4.x, `@teacher_required`, `Course.performance_dict`, `Course.refresh_performance_dict()`.

**Run tests with:**
```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_course_settings -v 2
```

---

## File map

| File | Action |
|---|---|
| `apps/teacher/views.py` | Update `course_detail_view`; add `course_settings_view` |
| `apps/teacher/urls.py` | Register `course-update-settings` route |
| `apps/teacher/templates/teacher/course_detail.html` | Add tab nav + Settings + Activity panels; remove dashboard links |
| `apps/teacher/tests/test_course_settings.py` | New |

---

## Task 1: Update `course_detail_view` and add `course_settings_view`

**Files:**
- Modify: `apps/teacher/views.py`
- Modify: `apps/teacher/urls.py`

- [ ] **Write failing tests**

Create `apps/teacher/tests/test_course_settings.py`:

```python
"""Tests for course Settings and Activity tabs."""
import json
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, ROLE_TEACHER
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered


def _make_teacher(email="t@t.com"):
    return User.objects.create_user(email=email, password="x", role=ROLE_TEACHER)


def _make_course(author, title="TC"):
    return Course.objects.create(
        title=title, authored_by=author,
        start_date=date(2026, 9, 1), end_date=date(2026, 12, 1),
    )


class CourseDetailTabsTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.course = _make_course(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")

    def test_default_tab_is_timeline(self):
        resp = self.client.get(reverse("teacher:course-detail", args=[self.course.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "timeline")

    def test_settings_tab_200(self):
        resp = self.client.get(
            reverse("teacher:course-detail", args=[self.course.id]) + "?tab=settings"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "settings")

    def test_activity_tab_200(self):
        resp = self.client.get(
            reverse("teacher:course-detail", args=[self.course.id]) + "?tab=activity"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["tab"], "activity")

    def test_no_dashboard_urls_in_context(self):
        resp = self.client.get(reverse("teacher:course-detail", args=[self.course.id]))
        self.assertNotIn("dashboard_edit_url", resp.context)
        self.assertNotIn("dashboard_activity_url", resp.context)


class CourseSettingsUpdateTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.course = _make_course(self.teacher)
        self.client = Client()
        self.client.login(email="t@t.com", password="x")
        self.url = reverse("teacher:course-update-settings", args=[self.course.id])

    def _post(self, payload):
        return self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

    def test_update_title(self):
        self._post({"title": "New Title"})
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "New Title")

    def test_update_dates(self):
        self._post({"start_date": "2026-10-01", "end_date": "2027-01-15"})
        self.course.refresh_from_db()
        self.assertEqual(self.course.start_date, date(2026, 10, 1))
        self.assertEqual(self.course.end_date, date(2027, 1, 15))

    def test_clear_dates(self):
        self._post({"start_date": None, "end_date": None})
        self.course.refresh_from_db()
        self.assertIsNone(self.course.start_date)
        self.assertIsNone(self.course.end_date)

    def test_start_after_end_rejected(self):
        resp = self._post({"start_date": "2027-01-01", "end_date": "2026-01-01"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_date_string_rejected(self):
        resp = self._post({"start_date": "not-a-date"})
        self.assertEqual(resp.status_code, 400)

    def test_other_teacher_cannot_update(self):
        other = _make_teacher(email="o@t.com")
        c = Client()
        c.login(email="o@t.com", password="x")
        resp = c.post(self.url, data=json.dumps({"title": "Stolen"}),
                      content_type="application/json")
        self.assertEqual(resp.status_code, 404)
```

- [ ] **Run to confirm failure**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_course_settings -v 2
```
Expected: FAIL — `NoReverseMatch` for `course-update-settings`.

- [ ] **Update `course_detail_view` in `apps/teacher/views.py`**

Find `course_detail_view`. Remove these lines:
```python
    dashboard_edit_url     = ...  # any URL to /dashboard/...
    dashboard_activity_url = ...  # any URL to /dashboard/...
```

Add `tab` to the context and remove the dashboard keys from `render(...)`:
```python
    tab = request.GET.get("tab", "timeline")
    return render(
        request,
        "teacher/course_detail.html",
        {
            "course":               course,
            "pco_rows":             pco_rows,         # Python list (replaces pco_rows_json)
            "pco_rows_json":        json.dumps(pco_rows),  # keep for JS window.__COURSE_DATA__
            "groups_json":          json.dumps(groups),
            "activity_json":        json.dumps(course.performance_dict),
            "addable_playlists_json": json.dumps(addable_playlists),
            "tab":                  tab,
        },
    )
```

Note: keep `pco_rows_json` for the existing JS; add `pco_rows` (the raw list) for use in template loops.

- [ ] **Add `course_settings_view` to `apps/teacher/views.py`**

```python
@teacher_required
@require_POST
def course_settings_view(request, course_id):
    """POST /teacher/courses/<course_id>/update-settings/"""
    from datetime import date as _date
    from django.views.decorators.http import require_POST as _rp
    course = get_object_or_404(Course, id=course_id, authored_by=request.user)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "title" in body:
        course.title = str(body["title"])[:200]

    def _parse_date(val):
        if val is None:
            return None
        try:
            return _date.fromisoformat(str(val))
        except ValueError:
            return "INVALID"

    new_start = _parse_date(body.get("start_date", "SKIP"))
    new_end   = _parse_date(body.get("end_date",   "SKIP"))
    if new_start == "INVALID" or new_end == "INVALID":
        return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)
    if new_start != "SKIP":
        course.start_date = new_start
    if new_end != "SKIP":
        course.end_date = new_end
    if course.start_date and course.end_date and course.start_date >= course.end_date:
        return JsonResponse({"error": "start_date must be before end_date."}, status=400)

    course.save()
    return JsonResponse({"ok": True})
```

Note: `"SKIP"` sentinel means the key wasn't in the payload — don't overwrite. `None` means clear the field.

- [ ] **Register URL in `apps/teacher/urls.py`**

Add to imports:
```python
from apps.teacher.views import course_settings_view
```

Add to `urlpatterns`:
```python
    path("courses/<str:course_id>/update-settings/", course_settings_view, name="course-update-settings"),
```

- [ ] **Run tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_course_settings -v 2
```
Expected: `test_no_dashboard_urls_in_context` may still fail until the template is updated (context key absent). The settings endpoint tests should pass.

- [ ] **Commit**

```bash
git add apps/teacher/views.py apps/teacher/urls.py \
        apps/teacher/tests/test_course_settings.py
git commit -m "feat: course settings endpoint; add tab to course_detail_view context"
```

---

## Task 2: Update `course_detail.html`

**Files:**
- Modify: `apps/teacher/templates/teacher/course_detail.html`

- [ ] **Add tab nav after the `t-list-header` div**

Find the `t-list-header` div (near the top of the template). After it, insert:

```html
<div class="t-tabs" style="margin-bottom:18px;">
  <a class="t-tab {% if tab == 'timeline' %}t-tab--active{% endif %}"
     href="?tab=timeline">Timeline</a>
  <a class="t-tab {% if tab == 'roster' %}t-tab--active{% endif %}"
     href="?tab=roster">Roster</a>
  <a class="t-tab {% if tab == 'settings' %}t-tab--active{% endif %}"
     href="?tab=settings">Settings</a>
  <a class="t-tab {% if tab == 'activity' %}t-tab--active{% endif %}"
     href="?tab=activity">Activity</a>
</div>
```

- [ ] **Wrap the existing `t-detail-layout` in a tab guard**

Wrap the main timeline/roster layout div with:
```html
{% if tab == 'timeline' or tab == 'roster' %}
  ... existing t-detail-layout ...
{% endif %}
```

- [ ] **Update `window.__COURSE_DATA__` block**

Remove `dashboardEditUrl` and `dashboardActivityUrl` entries. Add `settingsSaveUrl` and `csrfToken`:

```html
<script>
  window.__COURSE_DATA__ = {
    courseId:          "{{ course.id|escapejs }}",
    pcoRows:           {{ pco_rows_json|safe }},
    groups:            {{ groups_json|safe }},
    activity:          {{ activity_json|safe }},
    addablePlaylists:  {{ addable_playlists_json|safe }},
    csrfToken:         "{{ csrf_token }}",
    settingsSaveUrl:   "{% url 'teacher:course-update-settings' course.id %}",
  };
</script>
```

- [ ] **Add Settings tab panel (after the layout guard)**

```html
{% if tab == 'settings' %}
<div style="max-width:480px;">
  <div class="t-card">
    <div class="t-card-title">Course settings</div>

    <label class="t-label">Title</label>
    <input class="t-input" id="settings-title" type="text"
           value="{{ course.title|escapejs }}" maxlength="200">

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px;">
      <div>
        <label class="t-label">Start date</label>
        <input class="t-input" id="settings-start" type="date"
               value="{% if course.start_date %}{{ course.start_date|date:'Y-m-d' }}{% endif %}">
      </div>
      <div>
        <label class="t-label">End date</label>
        <input class="t-input" id="settings-end" type="date"
               value="{% if course.end_date %}{{ course.end_date|date:'Y-m-d' }}{% endif %}">
      </div>
    </div>

    <div style="margin-top:14px;">
      <button class="t-btn t-btn-primary" id="btn-settings-save">Save</button>
    </div>
    <p id="settings-msg" class="t-muted" style="margin-top:8px;display:none;"></p>
  </div>
</div>
<script>
document.getElementById("btn-settings-save").addEventListener("click", function() {
  var data = window.__COURSE_DATA__;
  var msg = document.getElementById("settings-msg");
  fetch(data.settingsSaveUrl, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRFToken": data.csrfToken},
    body: JSON.stringify({
      title:      document.getElementById("settings-title").value,
      start_date: document.getElementById("settings-start").value || null,
      end_date:   document.getElementById("settings-end").value || null,
    }),
  })
  .then(function(r) { return r.json(); })
  .then(function(j) {
    msg.style.display = "";
    msg.textContent = j.ok ? "Saved." : (j.error || "Error.");
  });
});
</script>
{% endif %}
```

- [ ] **Add Activity tab panel**

```html
{% if tab == 'activity' %}
<div>
  <div style="display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap;">
    <label class="t-label" style="margin:0;white-space:nowrap;">Filter by playlist:</label>
    <select class="t-input" id="activity-pl-filter" style="max-width:300px;">
      <option value="">All</option>
      {% for row in pco_rows %}
      <option value="{{ row.playlistId }}">{{ row.playlistName }}</option>
      {% endfor %}
    </select>
  </div>
  <div id="activity-table-container"></div>
  <p class="t-muted" style="margin-top:8px;">
    Data from <code>course.performance_dict</code> — reflects all recorded activity.
  </p>
</div>
<script>
(function() {
  var activity = window.__COURSE_DATA__.activity || {};
  var container = document.getElementById("activity-table-container");
  var entries = Object.entries(activity);
  if (!entries.length) {
    container.innerHTML = '<p class="t-muted">No activity recorded yet.</p>';
    return;
  }
  var rows = entries.map(function(kv) {
    var key = kv[0], val = kv[1];
    return '<tr>' +
      '<td>' + key + '</td>' +
      '<td>' + (val.pass_mark != null ? val.pass_mark : "—") + '</td>' +
      '<td>' + (val.attempts  != null ? val.attempts  : "—") + '</td>' +
      '<td>' + (val.time_spent_minutes != null ? val.time_spent_minutes + " min" : "—") + '</td>' +
    '</tr>';
  }).join('');
  container.innerHTML =
    '<table class="t-table"><thead><tr>' +
    '<th>Student / exercise</th><th>Status</th><th>Attempts</th><th>Time</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>';
})();
</script>
{% endif %}
```

- [ ] **Remove the `t-legacy-section` `<details>` block**

Find and delete the block:
```html
<details class="t-legacy-section">
  ...dashboard_activity_url...
</details>
```

- [ ] **Run all course settings tests**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests.test_course_settings -v 2
```
Expected: all pass (including `test_no_dashboard_urls_in_context`).

- [ ] **Run full teacher test suite to check for regressions**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py test --noinput apps.teacher.tests -v 2
```
Expected: all pass.

- [ ] **Browser smoke test**

1. Open a course detail page
2. Confirm Timeline tab loads as before (no regression)
3. Click Settings tab — form shows current title and dates
4. Edit title, click Save — success message appears; reload and confirm change persisted
5. Click Activity tab — table renders from `performance_dict` (may be empty for test courses)
6. Confirm no "Advanced / Legacy" or dashboard links visible to non-superuser

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/course_detail.html
git commit -m "feat: add Settings and Activity tabs to course detail; remove dashboard escape hatches"
```

---

## Self-review checklist

- [ ] `dashboard_edit_url` and `dashboard_activity_url` absent from both view context and template
- [ ] `<details class="t-legacy-section">` block deleted
- [ ] Activity filter dropdown uses `pco_rows` (Python list), not `pco_rows_json` (string)
- [ ] Start ≥ end date → 400 response, not 500
- [ ] Clearing a date (passing `null`) sets `course.start_date = None`
- [ ] Other teacher's course returns 404 from settings endpoint
- [ ] Timeline tab unchanged (existing tests pass)
