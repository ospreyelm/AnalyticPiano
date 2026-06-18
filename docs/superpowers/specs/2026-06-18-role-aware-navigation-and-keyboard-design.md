# Role-Aware Navigation and Keyboard Overlay Design

## Context

Three production symptoms share two missing contracts:

1. Teacher and superuser navigation is decided independently by the generic
   login view, project root redirect, student guard, and template links.
2. QWERTY shortcut labels depend on generated pixel coordinates, but the
   extracted exercise canvas CSS does not preserve the absolute-positioning
   rules that make those coordinates effective.

Observed production behavior:

- `GET /accounts/logout/` returns `405 Method Not Allowed` because Django's
  logout view accepts `POST`, while the teacher header renders a GET link.
- `/` redirects to `/s/`; the student staff guard then redirects a teacher to
  `/dashboard/`.
- QWERTY badges have generated `left` and `top` values but compute as
  `position: static`, so the browser ignores those coordinates.

## Goals

- Give each authenticated role one canonical home.
- Make all shared entry points use the same role-aware destination policy.
- Keep normal teacher workflows out of the legacy dashboard.
- Make logout method-correct and CSRF-protected.
- Make shortcut badges overlay their corresponding piano keys.
- Add a maintained URL map and regression coverage for the routing contract.

## Non-Goals

- Guest or demo access to the student app.
- Removing the legacy dashboard.
- Migrating every advanced dashboard tool into the teacher app.
- Redesigning the piano or changing keyboard shortcut mappings.
- Reworking student authentication beyond the shared destination policy.

Guest mode should be a separate feature with curated public exercises,
non-persistent or browser-local progress, and an explicit sign-up path.

## Canonical Destinations

| User state | Canonical home |
| --- | --- |
| Anonymous | `/s/login/` |
| Student | `/s/` |
| Teacher role | `/teacher/courses/` |
| Superuser | `/teacher/courses/` |

`is_staff` alone is not a product role. A staff user with the student role
should not silently become a teacher unless the account is also a superuser.
Existing administrative permissions remain unchanged.

## Architecture

### Shared destination resolver

Add a small account-level helper that returns a named URL or resolved path for
the current user:

- anonymous -> `student:login`
- `is_superuser` or `role == ROLE_TEACHER` -> `teacher:course-list`
- otherwise -> `student:home`

The helper owns role-to-home decisions. Views and guards call it rather than
embedding `/dashboard/`, `/s/`, or `/teacher/courses/` branches.

### Root route

Replace the unconditional project-level `RedirectView` for `/` with a small
view that uses the shared resolver:

- anonymous -> `/s/login/`
- student -> `/s/`
- teacher or superuser -> `/teacher/courses/`

The `/play/` compatibility redirect remains outside this change unless tests
show it participates in the broken flow.

### Login behavior

The generic `/accounts/login/` view uses the shared resolver after successful
authentication.

The dedicated `/s/login/` view remains student-facing. If an already
authenticated teacher or superuser reaches it, it redirects through the shared
resolver instead of entering the student app and relying on a later guard.

### Cross-app guards

The student guard redirects a teacher or superuser to the shared canonical
home, not `/dashboard/`.

Teacher authorization remains enforced by `teacher_required`; students cannot
enter teacher views.

### Header and brand links

Teacher brand/home links target `teacher:course-list`.
Student brand/home links continue to target `student:home`.

No authenticated teacher header link should route through `/` merely to
discover the user's role again.

### Logout

Use POST forms with CSRF tokens for logout in teacher, student, and retained
legacy headers. Do not expose GET logout links.

After logout, redirect to `student:login`, the role-neutral public entry point
for the current product. Guest mode may introduce a different public landing
page later.

## Keyboard Overlay Contract

The keyboard component generates badge coordinates relative to `.keyboard`.
The shared exercise canvas stylesheet must preserve:

```css
.keyboard {
  position: relative;
}

.keyboard .qwerty-key-badge {
  position: absolute;
}
```

The existing generated `left`, `top`, `width`, and `height` values then position
each badge over its rendered key. This applies to teacher Play and any student
surface that consumes the shared canvas stylesheet.

## URL Map

Add a concise maintained document covering public entry points and canonical
role destinations:

| Route | Anonymous | Student | Teacher / superuser |
| --- | --- | --- | --- |
| `/` | `/s/login/` | `/s/` | `/teacher/courses/` |
| `/accounts/login/` success | n/a | `/s/` | `/teacher/courses/` |
| `/s/login/` while authenticated | n/a | `/s/` | `/teacher/courses/` |
| `/s/` | `/s/login/?next=/s/` | render | `/teacher/courses/` |
| `/teacher/courses/` | login with `next` | denied | render |
| logout POST | `/s/login/` | `/s/login/` | `/s/login/` |

The map is a product contract, not generated output. Tests enforce its
behavioral rows.

## Testing

### Routing tests

Cover anonymous, student, teacher, and superuser behavior for:

- `/`
- generic login success
- authenticated `/s/login/`
- `/s/` cross-app guard
- teacher course access
- logout method and destination

Assert that normal teacher flows do not redirect to `/dashboard/`.

### Template tests

Assert:

- teacher sign out is a POST form with CSRF protection
- teacher brand points to `teacher:course-list`
- no teacher base-template sign-out GET link remains

### Keyboard tests

Static regression tests require both positioning declarations.

Browser verification on `/teacher/play/` measures:

- `.keyboard` computes as `position: relative`
- every visible `.qwerty-key-badge` computes as `position: absolute`
- badge bounds overlap the horizontal bounds of the corresponding rendered
  piano key
- labels do not collapse into a single normal-flow row

## Rollout

Ship routing and keyboard fixes together because both are small regressions in
the newly migrated teacher shell. Deploy from `.worktrees/master-run`, then
verify:

1. Teacher login lands on `/teacher/courses/`.
2. Visiting `/` as teacher lands on `/teacher/courses/`.
3. Teacher sign out succeeds and lands on `/s/login/`.
4. Student login and `/` land on `/s/`.
5. QWERTY labels align with white and black keys in `/teacher/play/`.

