"""DB-backed tests for course management views (Task 1).

Run with:
    DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test --noinput apps.teacher.tests.test_course_management_db -v 1
"""
import datetime
import json

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, Group, ROLE_TEACHER, ROLE_STUDENT
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered


# ---------------------------------------------------------------------------
# Shared helpers (mirror test_views_db.py)
# ---------------------------------------------------------------------------

def _make_teacher(**kwargs):
    defaults = dict(email="teacher@example.com", password="pass", role=ROLE_TEACHER)
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def _make_teacher2(**kwargs):
    defaults = dict(email="teacher2@example.com", password="pass", role=ROLE_TEACHER)
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def _make_student(**kwargs):
    defaults = dict(email="student@example.com", password="pass", role=ROLE_STUDENT)
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def _make_playlist(author, name="Test Playlist", skill_tags=None, is_public=False):
    pl = Playlist(
        name=name,
        authored_by=author,
        skill_tags=skill_tags or [],
        is_public=is_public,
    )
    pl.save()
    return pl


def _make_course(author, title="Test Course", start=None, end=None):
    course = Course(
        title=title,
        authored_by=author,
        open=False,
        start_date=start or datetime.date(2026, 9, 1),
        end_date=end or datetime.date(2026, 12, 15),
    )
    course.save()
    return course


def _make_pco(course, playlist, order, publish=None, due=None):
    tz = timezone.get_current_timezone()
    publish_dt = None
    due_dt = None
    if publish:
        publish_dt = timezone.make_aware(
            datetime.datetime.combine(publish, datetime.time(0, 0, 0)), tz
        )
    if due:
        due_dt = timezone.make_aware(
            datetime.datetime.combine(due, datetime.time(23, 59, 0)), tz
        )
    return PlaylistCourseOrdered.objects.create(
        course=course,
        playlist=playlist,
        order=order,
        publish_date=publish_dt,
        due_date=due_dt,
    )


def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------

class CourseManagementUrlTests(TestCase):

    def test_course_list_resolves(self):
        from apps.teacher.views import course_list_view
        from django.urls import resolve

        match = resolve("/teacher/courses/")
        self.assertEqual(match.func, course_list_view)

    def test_course_detail_resolves(self):
        from apps.teacher.views import course_detail_view
        from django.urls import resolve

        # Create a dummy course to get a valid id pattern
        match = resolve("/teacher/courses/C0001/")
        self.assertEqual(match.func, course_detail_view)

    def test_update_pco_resolves(self):
        from apps.teacher.views import update_pco_view
        from django.urls import resolve

        match = resolve("/teacher/courses/C0001/update-pco/")
        self.assertEqual(match.func, update_pco_view)

    def test_respread_resolves(self):
        from apps.teacher.views import respread_view
        from django.urls import resolve

        match = resolve("/teacher/courses/C0001/respread/")
        self.assertEqual(match.func, respread_view)

    def test_add_playlist_resolves(self):
        from apps.teacher.views import add_playlist_view
        from django.urls import resolve

        match = resolve("/teacher/courses/C0001/add-playlist/")
        self.assertEqual(match.func, add_playlist_view)


# ---------------------------------------------------------------------------
# course_list_view
# ---------------------------------------------------------------------------

class CourseListTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.teacher2 = _make_teacher2()
        self.client.force_login(self.teacher)

    def test_list_shows_own_courses(self):
        course = _make_course(self.teacher, title="My Course")
        resp = self.client.get(reverse("teacher:course-list"))
        self.assertEqual(resp.status_code, 200)
        courses = resp.context["courses"]
        ids = [c["id"] for c in courses]
        self.assertIn(course.id, ids)

    def test_list_does_not_show_other_teachers_courses(self):
        other_course = _make_course(self.teacher2, title="Not Mine")
        resp = self.client.get(reverse("teacher:course-list"))
        self.assertEqual(resp.status_code, 200)
        courses = resp.context["courses"]
        ids = [c["id"] for c in courses]
        self.assertNotIn(other_course.id, ids)

    def test_list_unit_count(self):
        course = _make_course(self.teacher)
        pl1 = _make_playlist(self.teacher, "P1")
        pl2 = _make_playlist(self.teacher, "P2")
        _make_pco(course, pl1, 1)
        _make_pco(course, pl2, 2)
        resp = self.client.get(reverse("teacher:course-list"))
        course_row = next(c for c in resp.context["courses"] if c["id"] == course.id)
        self.assertEqual(course_row["unit_count"], 2)

    def test_list_student_count(self):
        course = _make_course(self.teacher)
        student1 = _make_student(email="s1@example.com")
        student2 = _make_student(email="s2@example.com")
        group = Group(name="Section A", manager=self.teacher)
        group.save()
        group.members.add(student1, student2)
        course.visible_to.add(group)
        resp = self.client.get(reverse("teacher:course-list"))
        course_row = next(c for c in resp.context["courses"] if c["id"] == course.id)
        self.assertEqual(course_row["student_count"], 2)

    def test_list_anonymous_redirected(self):
        self.client.logout()
        resp = self.client.get(reverse("teacher:course-list"))
        self.assertEqual(resp.status_code, 302)

    def test_list_student_redirected(self):
        student = _make_student(email="student2@example.com")
        self.client.force_login(student)
        resp = self.client.get(reverse("teacher:course-list"))
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# course_detail_view
# ---------------------------------------------------------------------------

class CourseDetailContextTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.teacher2 = _make_teacher2()
        self.client.force_login(self.teacher)
        self.course = _make_course(self.teacher)
        self.pl1 = _make_playlist(self.teacher, "Unit 9 Roman", skill_tags=["mode:roman"])
        self.pl2 = _make_playlist(self.teacher, "Unit 10 Figures", skill_tags=["mode:figures"])
        self.pco1 = _make_pco(
            self.course, self.pl1, 1,
            publish=datetime.date(2026, 9, 1),
            due=datetime.date(2026, 10, 5),
        )
        self.pco2 = _make_pco(
            self.course, self.pl2, 2,
            publish=datetime.date(2026, 10, 6),
            due=datetime.date(2026, 11, 10),
        )
        self.url = reverse("teacher:course-detail", args=[self.course.id])

    def test_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_course_in_context(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["course"], self.course)

    def test_pco_rows_json_order(self):
        resp = self.client.get(self.url)
        rows = json.loads(resp.context["pco_rows_json"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["order"], 1)
        self.assertEqual(rows[1]["order"], 2)
        # pcoId values present
        self.assertEqual(rows[0]["pcoId"], self.pco1.pk)
        self.assertEqual(rows[1]["pcoId"], self.pco2.pk)

    def test_pco_rows_json_mode(self):
        resp = self.client.get(self.url)
        rows = json.loads(resp.context["pco_rows_json"])
        self.assertEqual(rows[0]["mode"], "roman")
        self.assertEqual(rows[1]["mode"], "figures")

    def test_pco_rows_json_dates(self):
        resp = self.client.get(self.url)
        rows = json.loads(resp.context["pco_rows_json"])
        self.assertEqual(rows[0]["publish"], "2026-09-01")
        self.assertEqual(rows[0]["due"], "2026-10-05")

    def test_groups_in_context(self):
        student = _make_student()
        group = Group(name="Section A", manager=self.teacher)
        group.save()
        group.members.add(student)
        self.course.visible_to.add(group)
        resp = self.client.get(self.url)
        groups = resp.context["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["name"], "Section A")
        self.assertEqual(groups[0]["member_count"], 1)
        self.assertIsNotNone(groups[0]["join_code"])
        self.assertEqual(len(groups[0]["members"]), 1)

    def test_addable_playlists_includes_own(self):
        resp = self.client.get(self.url)
        addable = json.loads(resp.context["addable_playlists_json"])
        ids = [p["id"] for p in addable]
        self.assertIn(self.pl1.id, ids)

    def test_addable_playlists_includes_public(self):
        pub_pl = _make_playlist(self.teacher2, "Public Playlist", is_public=True)
        resp = self.client.get(self.url)
        addable = json.loads(resp.context["addable_playlists_json"])
        ids = [p["id"] for p in addable]
        self.assertIn(pub_pl.id, ids)

    def test_addable_playlists_excludes_other_private(self):
        priv_pl = _make_playlist(self.teacher2, "Private Other", is_public=False)
        resp = self.client.get(self.url)
        addable = json.loads(resp.context["addable_playlists_json"])
        ids = [p["id"] for p in addable]
        self.assertNotIn(priv_pl.id, ids)

    def test_addable_playlists_source_field(self):
        resp = self.client.get(self.url)
        addable = json.loads(resp.context["addable_playlists_json"])
        mine = next(p for p in addable if p["id"] == self.pl1.id)
        self.assertEqual(mine["source"], "mine")

    def test_dashboard_urls_in_context(self):
        resp = self.client.get(self.url)
        self.assertIn("dashboard_edit_url", resp.context)
        self.assertIn("dashboard_activity_url", resp.context)
        self.assertIn(self.course.id, resp.context["dashboard_edit_url"])
        self.assertIn(self.course.id, resp.context["dashboard_activity_url"])

    def test_other_teachers_course_404(self):
        other_course = _make_course(self.teacher2, title="Other Course")
        url = reverse("teacher:course-detail", args=[other_course.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# update_pco_view
# ---------------------------------------------------------------------------

class UpdatePcoTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.teacher2 = _make_teacher2()
        self.client.force_login(self.teacher)
        self.course = _make_course(self.teacher)
        self.pl = _make_playlist(self.teacher, "Unit 9 Roman")
        self.pco = _make_pco(
            self.course, self.pl, 1,
            publish=datetime.date(2026, 9, 1),
            due=datetime.date(2026, 10, 5),
        )
        self.url = reverse("teacher:course-update-pco", args=[self.course.id])

    def test_update_publish_and_due(self):
        payload = {
            "changes": [
                {
                    "pcoId": self.pco.pk,
                    "publish": "2026-09-15",
                    "due": "2026-10-20",
                }
            ],
            "removals": [],
        }
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 200)
        self.pco.refresh_from_db()
        tz = timezone.get_current_timezone()
        local_publish = self.pco.publish_date.astimezone(tz).date()
        local_due = self.pco.due_date.astimezone(tz).date()
        self.assertEqual(local_publish, datetime.date(2026, 9, 15))
        self.assertEqual(local_due, datetime.date(2026, 10, 20))

    def test_update_publish_tz_aware(self):
        payload = {
            "changes": [{"pcoId": self.pco.pk, "publish": "2026-09-15"}],
            "removals": [],
        }
        _post_json(self.client, self.url, payload)
        self.pco.refresh_from_db()
        self.assertIsNotNone(self.pco.publish_date.tzinfo)
        tz = timezone.get_current_timezone()
        self.assertEqual(self.pco.publish_date.astimezone(tz).time(), datetime.time(0, 0, 0))

    def test_update_due_tz_aware(self):
        payload = {
            "changes": [{"pcoId": self.pco.pk, "due": "2026-10-20"}],
            "removals": [],
        }
        _post_json(self.client, self.url, payload)
        self.pco.refresh_from_db()
        self.assertIsNotNone(self.pco.due_date.tzinfo)
        tz = timezone.get_current_timezone()
        self.assertEqual(self.pco.due_date.astimezone(tz).time(), datetime.time(23, 59, 0))

    def test_update_order(self):
        payload = {
            "changes": [{"pcoId": self.pco.pk, "order": 5}],
            "removals": [],
        }
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 200)
        self.pco.refresh_from_db()
        self.assertEqual(self.pco.order, 5)

    def test_removal_deletes_pco(self):
        payload = {"changes": [], "removals": [self.pco.pk]}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            PlaylistCourseOrdered.objects.filter(pk=self.pco.pk).exists()
        )

    def test_pco_from_another_course_400(self):
        other_course = _make_course(self.teacher, title="Other Course")
        other_pl = _make_playlist(self.teacher, "Other PL")
        other_pco = _make_pco(other_course, other_pl, 1)
        payload = {
            "changes": [{"pcoId": other_pco.pk, "order": 1}],
            "removals": [],
        }
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_removal_from_another_course_400(self):
        other_course = _make_course(self.teacher, title="Other Course 2")
        other_pl = _make_playlist(self.teacher, "Other PL 2")
        other_pco = _make_pco(other_course, other_pl, 1)
        payload = {"changes": [], "removals": [other_pco.pk]}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_null_publish_clears_date(self):
        payload = {
            "changes": [{"pcoId": self.pco.pk, "publish": None}],
            "removals": [],
        }
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 200)
        self.pco.refresh_from_db()
        self.assertIsNone(self.pco.publish_date)

    def test_authz_other_teachers_course_404(self):
        other_course = _make_course(self.teacher2, title="Other Teacher Course")
        url = reverse("teacher:course-update-pco", args=[other_course.id])
        payload = {"changes": [], "removals": []}
        resp = _post_json(self.client, url, payload)
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# respread_view
# ---------------------------------------------------------------------------

class RespreadTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.teacher2 = _make_teacher2()
        self.client.force_login(self.teacher)
        self.course = _make_course(
            self.teacher,
            start=datetime.date(2026, 9, 1),
            end=datetime.date(2026, 12, 14),
        )
        self.pl1 = _make_playlist(self.teacher, "PL1")
        self.pl2 = _make_playlist(self.teacher, "PL2")
        self.pl3 = _make_playlist(self.teacher, "PL3")
        self.pco1 = _make_pco(self.course, self.pl1, 1)
        self.pco2 = _make_pco(self.course, self.pl2, 2)
        self.pco3 = _make_pco(self.course, self.pl3, 3)
        self.url = reverse("teacher:course-respread", args=[self.course.id])

    def test_respread_rewrites_dates(self):
        payload = {"fromOrder": 1, "publishAllAtStart": False}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 200)
        for pco in [self.pco1, self.pco2, self.pco3]:
            pco.refresh_from_db()
            self.assertIsNotNone(pco.publish_date)
            self.assertIsNotNone(pco.due_date)

    def test_respread_due_weekday_sunday(self):
        payload = {"fromOrder": 1, "publishAllAtStart": False}
        _post_json(self.client, self.url, payload)
        tz = timezone.get_current_timezone()
        for pco in [self.pco1, self.pco2, self.pco3]:
            pco.refresh_from_db()
            due_date = pco.due_date.astimezone(tz).date()
            # Sunday = weekday 6
            self.assertEqual(due_date.weekday(), 6, f"Expected Sunday, got {due_date}")

    def test_respread_due_dates_increasing(self):
        payload = {"fromOrder": 1, "publishAllAtStart": False}
        _post_json(self.client, self.url, payload)
        tz = timezone.get_current_timezone()
        pcos = [self.pco1, self.pco2, self.pco3]
        for pco in pcos:
            pco.refresh_from_db()
        due_dates = [pco.due_date.astimezone(tz).date() for pco in pcos]
        self.assertEqual(due_dates, sorted(due_dates))

    def test_respread_due_dates_lte_end_date(self):
        payload = {"fromOrder": 1, "publishAllAtStart": False}
        _post_json(self.client, self.url, payload)
        tz = timezone.get_current_timezone()
        for pco in [self.pco1, self.pco2, self.pco3]:
            pco.refresh_from_db()
            due_date = pco.due_date.astimezone(tz).date()
            self.assertLessEqual(due_date, self.course.end_date)

    def test_respread_from_order_skips_earlier(self):
        # Give pco1 a known date before respreading from order 2
        tz = timezone.get_current_timezone()
        known_date = timezone.make_aware(
            datetime.datetime.combine(datetime.date(2026, 8, 1), datetime.time(0, 0, 0)), tz
        )
        self.pco1.publish_date = known_date
        self.pco1.save()

        payload = {"fromOrder": 2, "publishAllAtStart": False}
        _post_json(self.client, self.url, payload)
        self.pco1.refresh_from_db()
        # pco1 should be untouched
        self.assertEqual(self.pco1.publish_date.astimezone(tz).date(), datetime.date(2026, 8, 1))

    def test_respread_400_without_end_date(self):
        self.course.end_date = None
        self.course.save()
        payload = {"fromOrder": 1, "publishAllAtStart": False}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_respread_400_no_rows_at_from_order(self):
        payload = {"fromOrder": 999, "publishAllAtStart": False}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_authz_other_teachers_course_404(self):
        other_course = _make_course(self.teacher2, title="Other Teacher Course")
        url = reverse("teacher:course-respread", args=[other_course.id])
        payload = {"fromOrder": 1, "publishAllAtStart": False}
        resp = _post_json(self.client, url, payload)
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# add_playlist_view
# ---------------------------------------------------------------------------

class AddPlaylistTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = _make_teacher()
        self.teacher2 = _make_teacher2()
        self.client.force_login(self.teacher)
        self.course = _make_course(self.teacher)
        self.pl = _make_playlist(self.teacher, "Own Playlist")
        self.url = reverse("teacher:course-add-playlist", args=[self.course.id])

    def test_add_own_playlist(self):
        payload = {"playlistId": self.pl.id}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            PlaylistCourseOrdered.objects.filter(course=self.course, playlist=self.pl).exists()
        )

    def test_add_appends_at_next_order(self):
        existing_pl = _make_playlist(self.teacher, "Existing")
        _make_pco(self.course, existing_pl, 5)
        payload = {"playlistId": self.pl.id}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 201)
        pco = PlaylistCourseOrdered.objects.get(course=self.course, playlist=self.pl)
        self.assertEqual(pco.order, 6)

    def test_add_public_playlist_from_other_teacher(self):
        pub_pl = _make_playlist(self.teacher2, "Public PL", is_public=True)
        payload = {"playlistId": pub_pl.id}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 201)

    def test_add_private_other_teacher_playlist_400(self):
        priv_pl = _make_playlist(self.teacher2, "Private PL", is_public=False)
        payload = {"playlistId": priv_pl.id}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_add_nonexistent_playlist_400(self):
        payload = {"playlistId": "PA00NONEXISTENT"}
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_add_with_publish_and_due(self):
        payload = {
            "playlistId": self.pl.id,
            "publish": "2026-09-01",
            "due": "2026-10-05",
        }
        resp = _post_json(self.client, self.url, payload)
        self.assertEqual(resp.status_code, 201)
        pco = PlaylistCourseOrdered.objects.get(course=self.course, playlist=self.pl)
        tz = timezone.get_current_timezone()
        self.assertIsNotNone(pco.publish_date)
        self.assertIsNotNone(pco.due_date)
        self.assertEqual(pco.publish_date.astimezone(tz).date(), datetime.date(2026, 9, 1))
        self.assertEqual(pco.due_date.astimezone(tz).date(), datetime.date(2026, 10, 5))
        self.assertEqual(pco.publish_date.astimezone(tz).time(), datetime.time(0, 0, 0))
        self.assertEqual(pco.due_date.astimezone(tz).time(), datetime.time(23, 59, 0))

    def test_authz_other_teachers_course_404(self):
        other_course = _make_course(self.teacher2, title="Other Teacher Course")
        url = reverse("teacher:course-add-playlist", args=[other_course.id])
        payload = {"playlistId": self.pl.id}
        resp = _post_json(self.client, url, payload)
        self.assertEqual(resp.status_code, 404)
