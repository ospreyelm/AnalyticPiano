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

## Role Definitions & Capabilities

- **ROLE_STUDENT**: Normal student user role. Lands on `/s/`.
- **ROLE_TEACHER**: Teacher user role. Lands on `/teacher/courses/`.
- **Superuser**: Lands on `/teacher/courses/` and has teacher access.
- **is_staff**: An administrative capability (e.g. Django admin access), not a teacher product role. A user with `is_staff=True` but `role=ROLE_STUDENT` will not be routed to teacher pages, and will still be allowed to access student views.
