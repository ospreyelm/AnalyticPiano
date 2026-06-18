# Role-Aware Navigation and Keyboard Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/`, login, student guards, headers, and logout follow one role-aware navigation contract, while restoring absolute positioning for piano shortcut badges.

**Architecture:** Add one account-level destination resolver and reuse it at every shared entry point. Keep teacher and student authorization in their existing apps, but remove embedded dashboard destinations from normal teacher flows. Preserve the piano component's generated coordinates by restoring both positioning declarations in the shared canvas CSS.

**Tech Stack:** Django 5.2 views/templates/tests, Python, CSS, RequireJS piano component, browser DOM geometry verification.

---

## File Map

- Create `apps/accounts/navigation.py`: canonical role-to-home resolver.
- Create `apps/accounts/tests/test_navigation.py`: resolver, root, and logout contract tests.
- Modify `apps/accounts/views.py`: use resolver after generic login; set logout destination.
- Modify `harmony/views.py`: add role-aware root view.
- Modify `harmony/urls.py`: mount the root view instead of unconditional `RedirectView`.
- Modify `apps/student/views.py`: route authenticated teachers away from student login and student views.
- Modify `apps/student/templates/student/base.html`: POST logout form.
- Modify `apps/student/static/student/student.css`: student sign-out button reset.
- Modify `apps/teacher/templates/teacher/base.html`: canonical brand link and POST logout form.
- Modify `apps/teacher/static/teacher/teacher.css`: teacher sign-out button reset.
- Modify `apps/teacher/tests/test_views_db.py`: teacher header contract tests.
- Modify `apps/student/tests/test_views.py`: student login, guard, and logout contract tests.
- Modify `apps/accounts/tests/test_login_redirects.py`: student generic login now lands on the modern student home.
- Modify `apps/student/static/student/exercise-canvas.css`: absolute shortcut badge positioning.
- Modify `lab/tests/test_play_view.py`: require both keyboard positioning declarations.
- Create `docs/navigation_map.md`: maintained route behavior table and guest-mode boundary.

### Task 1: Canonical Destination Resolver and Root Route

**Files:**
- Create: `apps/accounts/navigation.py`
- Create: `apps/accounts/tests/test_navigation.py`
- Modify: `harmony/views.py`
- Modify: `harmony/urls.py`

- [ ] **Step 1: Write failing resolver and root-route tests**

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ROLE_STUDENT, ROLE_TEACHER
from apps.accounts.navigation import home_url_for_user


class HomeDestinationTests(TestCase):
    def test_anonymous_destination_is_student_login(self):
        self.assertEqual(
            home_url_for_user(AnonymousUser()),
            reverse("student:login"),
        )

    def test_root_routes_anonymous_to_student_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, reverse("student:login"), fetch_redirect_response=False)

    def test_root_routes_student_to_student_home(self):
        user = get_user_model().objects.create_user(
            email="student-root@example.com", password="pass", role=ROLE_STUDENT
        )
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("student:home"), fetch_redirect_response=False)

    def test_root_routes_teacher_to_teacher_courses(self):
        user = get_user_model().objects.create_user(
            email="teacher-root@example.com", password="pass", role=ROLE_TEACHER
        )
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("teacher:course-list"), fetch_redirect_response=False)

    def test_root_routes_superuser_to_teacher_courses(self):
        user = get_user_model().objects.create_superuser(
            email="super-root@example.com", password="pass"
        )
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("teacher:course-list"), fetch_redirect_response=False)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test \
  --noinput apps.accounts.tests.test_navigation -v 2
```

Expected: import failure for `apps.accounts.navigation` or root still redirects to `/s/`.

- [ ] **Step 3: Implement the resolver and root view**

```python
# apps/accounts/navigation.py
from django.urls import reverse

from apps.accounts.models import ROLE_TEACHER


def home_url_for_user(user):
    if not user.is_authenticated:
        return reverse("student:login")
    if user.is_superuser or user.role == ROLE_TEACHER:
        return reverse("teacher:course-list")
    return reverse("student:home")
```

```python
# harmony/views.py
from django.shortcuts import redirect, render

from apps.accounts.navigation import home_url_for_user


def home_redirect(request):
    return redirect(home_url_for_user(request.user))
```

Replace the root `RedirectView` route:

```python
from harmony.views import home_redirect

path("", home_redirect, name="root-redirect"),
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run the Task 1 command. Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/navigation.py apps/accounts/tests/test_navigation.py harmony/views.py harmony/urls.py
git commit -m "Add role-aware home routing"
```

### Task 2: Login and Student Guard Alignment

**Files:**
- Modify: `apps/accounts/tests/test_login_redirects.py`
- Modify: `apps/accounts/views.py`
- Modify: `apps/student/tests/test_views.py`
- Modify: `apps/student/views.py`

- [ ] **Step 1: Write failing login and guard assertions**

Change the generic student login expectation:

```python
def test_student_role_redirects_to_student_home(self):
    student = get_user_model().objects.create_user(
        email="student@example.com",
        password=self.password,
        role=ROLE_STUDENT,
    )
    response = self._login(student)
    self.assertRedirects(
        response,
        reverse("student:home"),
        fetch_redirect_response=False,
    )
```

Update/add student view tests:

```python
def test_authenticated_teacher_login_get_redirects_to_teacher_courses(self):
    self.instructor.role = ROLE_TEACHER
    self.instructor.save(update_fields=["role"])
    self.client.force_login(self.instructor)
    response = self.client.get(reverse("student:login"))
    self.assertRedirects(
        response,
        reverse("teacher:course-list"),
        fetch_redirect_response=False,
    )

def test_home_redirects_teacher_to_teacher_courses(self):
    self.instructor.role = ROLE_TEACHER
    self.instructor.save(update_fields=["role"])
    self.client.force_login(self.instructor)
    response = self.client.get(reverse("student:home"))
    self.assertRedirects(
        response,
        reverse("teacher:course-list"),
        fetch_redirect_response=False,
    )

def test_staff_student_is_not_treated_as_teacher(self):
    staff_student = User.objects.create_user(
        email="staff-student@example.com",
        password="testpass123",
        role=ROLE_STUDENT,
        is_staff=True,
    )
    self.client.force_login(staff_student)
    response = self.client.get(reverse("student:home"))
    self.assertEqual(response.status_code, 200)
```

Import `ROLE_STUDENT` and `ROLE_TEACHER` in the test module.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test \
  --noinput apps.accounts.tests.test_login_redirects \
  apps.student.tests.test_views.StudentBasicViewTests -v 2
```

Expected: student generic login points to `/dashboard/my-work/`; teacher student-app requests point to `/dashboard/`; staff-student is incorrectly redirected.

- [ ] **Step 3: Use the resolver in login and student boundaries**

In `apps/accounts/views.py`:

```python
from .navigation import home_url_for_user

# after django_login(request, user)
return redirect(home_url_for_user(user))
```

In `StudentLoginView.get`:

```python
if request.user.is_authenticated:
    return redirect(home_url_for_user(request.user))
```

Replace `_require_student`'s staff check:

```python
if request.user.is_superuser or request.user.role == ROLE_TEACHER:
    return redirect(home_url_for_user(request.user))
```

Import `ROLE_TEACHER` and `home_url_for_user`; remove `HttpResponseRedirect` if no longer used.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Task 2 command. Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/views.py apps/accounts/tests/test_login_redirects.py \
  apps/student/views.py apps/student/tests/test_views.py
git commit -m "Align login and student guards with role homes"
```

### Task 3: Method-Correct Logout and Header Links

**Files:**
- Modify: `apps/accounts/tests/test_navigation.py`
- Modify: `apps/accounts/views.py`
- Modify: `apps/student/views.py`
- Modify: `apps/student/templates/student/base.html`
- Modify: `apps/student/static/student/student.css`
- Modify: `apps/teacher/templates/teacher/base.html`
- Modify: `apps/teacher/static/teacher/teacher.css`
- Modify: `apps/teacher/tests/test_views_db.py`
- Modify: `apps/student/tests/test_views.py`

- [ ] **Step 1: Write failing logout and template tests**

Add logout behavior:

```python
class LogoutContractTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="logout@example.com", password="pass", role=ROLE_STUDENT
        )
        self.client.force_login(self.user)

    def test_logout_get_is_not_allowed(self):
        response = self.client.get(reverse("custom-logout"))
        self.assertEqual(response.status_code, 405)

    def test_logout_post_redirects_to_student_login(self):
        response = self.client.post(reverse("custom-logout"))
        self.assertRedirects(
            response,
            reverse("student:login"),
            fetch_redirect_response=False,
        )
```

Add teacher template assertions:

```python
def test_teacher_header_uses_canonical_brand_and_post_logout(self):
    teacher = _make_teacher()
    client = Client()
    client.force_login(teacher)
    response = client.get(reverse("teacher:course-list"))
    self.assertContains(response, f'href="{reverse("teacher:course-list")}"')
    self.assertContains(response, 'method="post"')
    self.assertContains(response, f'action="{reverse("custom-logout")}"')
    self.assertNotContains(response, 'href="/accounts/logout/"')
```

Add student template assertions:

```python
def test_student_header_uses_post_logout(self):
    self.client.force_login(self.student)
    response = self.client.get(reverse("student:home"))
    self.assertContains(response, 'method="post"')
    self.assertContains(response, f'action="{reverse("custom-logout")}"')
    self.assertNotContains(response, f'href="{reverse("student:logout")}"')
```

Add student logout endpoint assertions:

```python
def test_student_logout_get_is_not_allowed(self):
    self.client.force_login(self.student)
    response = self.client.get(reverse("student:logout"))
    self.assertEqual(response.status_code, 405)

def test_student_logout_post_redirects_to_student_login(self):
    self.client.force_login(self.student)
    response = self.client.post(reverse("student:logout"))
    self.assertRedirects(
        response,
        reverse("student:login"),
        fetch_redirect_response=False,
    )
```

- [ ] **Step 2: Run focused tests and verify RED**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test \
  --noinput apps.accounts.tests.test_navigation \
  apps.teacher.tests.test_views_db.TeacherBaseTemplateTests \
  apps.student.tests.test_views.StudentBasicViewTests -v 2
```

Expected: logout POST redirects via `lab:index`, teacher brand points to `/`, and teacher/student headers contain GET logout links.

- [ ] **Step 3: Implement POST logout forms and destination**

Set:

```python
class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy("student:login")
```

Make the retained student endpoint POST-only:

```python
class StudentLogoutView(View):
    def post(self, request):
        django_logout(request)
        return redirect(reverse("student:login"))
```

Teacher header:

```django
<a class="t-header-brand" href="{% url 'teacher:course-list' %}">Monteverdi</a>
...
<form method="post" action="{% url 'custom-logout' %}" class="t-header-signout-form">
  {% csrf_token %}
  <button type="submit" class="t-header-signout">Sign out</button>
</form>
```

Student header:

```django
<form method="post" action="{% url 'custom-logout' %}">
  {% csrf_token %}
  <button type="submit" class="s-header-signout">Sign out</button>
</form>
```

Add explicit button resets:

```css
/* apps/teacher/static/teacher/teacher.css */
.t-header-signout {
  appearance: none;
  padding: 0;
  border: 0;
  background: transparent;
  font-family: inherit;
  cursor: pointer;
  font-size: 0.78rem;
  color: #ffd;
  opacity: 0.85;
}
```

```css
/* apps/student/static/student/student.css */
.s-header-signout {
  appearance: none;
  padding: 0;
  border: 0;
  background: transparent;
  color: #e74c3c;
  font: inherit;
  font-size: 0.8rem;
  cursor: pointer;
}
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Task 3 command. Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/views.py apps/accounts/tests/test_navigation.py apps/student/views.py \
  apps/teacher/templates/teacher/base.html apps/teacher/static/teacher/teacher.css \
  apps/teacher/tests/test_views_db.py apps/student/templates/student/base.html \
  apps/student/static/student/student.css apps/student/tests/test_views.py
git commit -m "Use POST logout across modern app headers"
```

### Task 4: Keyboard Shortcut Overlay Positioning

**Files:**
- Modify: `apps/student/static/student/exercise-canvas.css`
- Modify: `lab/tests/test_play_view.py`

- [ ] **Step 1: Strengthen the failing CSS regression**

Add the missing contract assertion:

```python
self.assertIn(".keyboard .qwerty-key-badge {", css)
self.assertIn("position: absolute", css)
```

Do not rely only on the broad `position: relative` substring assertion; require both selectors.

- [ ] **Step 2: Run the test and verify RED**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test \
  --noinput lab.tests.test_play_view.PlayViewTeacherChromeTests.test_exercise_canvas_css_preserves_staff_and_keyboard_layout_rules -v 2
```

Expected: FAIL because `.qwerty-key-badge` computes from CSS without `position: absolute`.

- [ ] **Step 3: Restore the overlay rule**

```css
.keyboard .qwerty-key-badge {
  position: absolute;
  display: inline-flex;
  ...
}
```

Keep `.keyboard { position: relative; }`. Do not alter JavaScript coordinates or add manual label nudges.

- [ ] **Step 4: Run the test and verify GREEN**

Run the Task 4 command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/student/static/student/exercise-canvas.css lab/tests/test_play_view.py
git commit -m "Restore absolute piano shortcut overlays"
```

### Task 5: Maintained URL Map

**Files:**
- Create: `docs/navigation_map.md`

- [ ] **Step 1: Write the route contract document**

Include:

```markdown
# Navigation Map

| Route | Anonymous | Student | Teacher / superuser |
| --- | --- | --- | --- |
| `/` | `/s/login/` | `/s/` | `/teacher/courses/` |
| `/accounts/login/` success | n/a | `/s/` | `/teacher/courses/` |
| `/s/login/` authenticated | n/a | `/s/` | `/teacher/courses/` |
| `/s/` | `/s/login/?next=/s/` | render | `/teacher/courses/` |
| `/teacher/courses/` | login with `next` | denied | render |
| logout POST | `/s/login/` | `/s/login/` | `/s/login/` |

## Guest Mode

Anonymous student/demo use is intentionally out of scope. A future guest mode
must use a separate route and must not impersonate an enrolled student session.
```

Also state that `is_staff` is an administrative capability, not a teacher product role.

- [ ] **Step 2: Check the document against route tests**

Compare every row to tests in `test_navigation.py`, `test_login_redirects.py`, and `test_views.py`. Add a missing test before continuing if any documented behavior is untested.

- [ ] **Step 3: Commit**

```bash
git add docs/navigation_map.md
git commit -m "Document canonical application routes"
```

### Task 6: Full Verification and Browser Geometry

**Files:**
- No production changes expected.

- [ ] **Step 1: Run the focused regression suite**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput \
  apps.accounts.tests.test_navigation \
  apps.accounts.tests.test_login_redirects \
  apps.student.tests.test_views.StudentBasicViewTests \
  apps.teacher.tests.test_views_db.TeacherBaseTemplateTests \
  apps.teacher.tests.test_views_db.TeacherRequiredTests \
  lab.tests.test_play_view -v 1
```

Expected: all tests pass.

- [ ] **Step 2: Run system and diff checks**

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py check
git diff --check origin/master...HEAD
git status --short --branch
```

Expected: Django check succeeds with only the existing CKEditor warning; no diff whitespace errors; worktree clean.

- [ ] **Step 3: Verify route behavior in a browser**

Using local test accounts or the existing authenticated browser session:

1. Teacher login -> `/teacher/courses/`.
2. Teacher visits `/` -> `/teacher/courses/`.
3. Teacher visits `/s/` -> `/teacher/courses/`.
4. Teacher sign out POST -> `/s/login/`.
5. Student login -> `/s/`.
6. Student visits `/` -> `/s/`.

Record actual final URLs; no normal teacher path may end at `/dashboard/`.

- [ ] **Step 4: Verify keyboard geometry**

On `/teacher/play/`, evaluate:

```javascript
({
  keyboardPosition: getComputedStyle(document.querySelector(".keyboard")).position,
  badgePositions: [...document.querySelectorAll(".qwerty-key-badge")]
    .map((badge) => getComputedStyle(badge).position),
})
```

Expected:

- `keyboardPosition === "relative"`
- every badge position is `"absolute"`
- screenshot shows white-key labels near white-key bottoms and black-key labels near black-key bottoms
- badges do not form a single horizontal normal-flow row

- [ ] **Step 5: Commit verification adjustments only if files changed**

```bash
git add apps/accounts/navigation.py apps/accounts/views.py apps/accounts/tests/test_navigation.py \
  apps/accounts/tests/test_login_redirects.py apps/student/views.py \
  apps/student/templates/student/base.html apps/student/static/student/student.css \
  apps/student/static/student/exercise-canvas.css apps/student/tests/test_views.py \
  apps/teacher/templates/teacher/base.html apps/teacher/static/teacher/teacher.css \
  apps/teacher/tests/test_views_db.py harmony/views.py harmony/urls.py \
  lab/tests/test_play_view.py docs/navigation_map.md
git commit -m "Complete navigation contract verification"
```

Do not create an empty commit.

### Task 7: Publish for Review

- [ ] **Step 1: Push the branch**

```bash
git push origin codex/navigation-contract
```

- [ ] **Step 2: Open a PR against Avner's repository**

```bash
gh pr create \
  --repo avnerdorman/HarmonyLab \
  --base master \
  --head codex/navigation-contract \
  --title "Unify role-aware navigation and keyboard overlays" \
  --body-file /tmp/harmonylab-navigation-contract-pr.md
```

Before running the command, create `/tmp/harmonylab-navigation-contract-pr.md`
with this content:

```markdown
## Summary
- add one role-aware home resolver for root, login, and cross-app guards
- route teachers and superusers to `/teacher/courses/` and students to `/s/`
- replace modern-app GET logout links with CSRF-protected POST forms
- restore absolute positioning for QWERTY piano shortcut badges
- document the canonical URL map and guest-mode boundary

## Verification
- focused Django navigation, template, and play-view tests pass
- `python3 manage.py check` succeeds with the existing CKEditor warning only
- browser route checks end at the documented canonical destinations
- browser geometry shows a relative keyboard and absolute shortcut badges
```
