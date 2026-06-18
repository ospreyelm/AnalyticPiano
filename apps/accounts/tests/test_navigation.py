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

    def test_student_destination_is_student_home(self):
        student = get_user_model()(role=ROLE_STUDENT)

        self.assertEqual(
            home_url_for_user(student),
            reverse("student:home"),
        )

    def test_teacher_destination_is_teacher_courses(self):
        teacher = get_user_model()(role=ROLE_TEACHER)

        self.assertEqual(
            home_url_for_user(teacher),
            reverse("teacher:course-list"),
        )

    def test_superuser_destination_is_teacher_courses(self):
        superuser = get_user_model()(role=ROLE_STUDENT, is_superuser=True)

        self.assertEqual(
            home_url_for_user(superuser),
            reverse("teacher:course-list"),
        )

    def test_staff_student_destination_is_student_home(self):
        staff_student = get_user_model()(role=ROLE_STUDENT, is_staff=True)

        self.assertEqual(
            home_url_for_user(staff_student),
            reverse("student:home"),
        )

    def test_root_routes_anonymous_to_student_login(self):
        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("student:login"),
            fetch_redirect_response=False,
        )

    def test_root_routes_student_to_student_home(self):
        user = get_user_model().objects.create_user(
            email="student-root@example.com",
            password="pass",
            role=ROLE_STUDENT,
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("student:home"),
            fetch_redirect_response=False,
        )

    def test_root_routes_teacher_to_teacher_courses(self):
        user = get_user_model().objects.create_user(
            email="teacher-root@example.com",
            password="pass",
            role=ROLE_TEACHER,
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )

    def test_root_routes_superuser_to_teacher_courses(self):
        user = get_user_model().objects.create_superuser(
            email="super-root@example.com",
            password="pass",
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )

    def test_root_routes_staff_student_to_student_home(self):
        user = get_user_model().objects.create_user(
            email="staff-student-root@example.com",
            password="pass",
            role=ROLE_STUDENT,
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("student:home"),
            fetch_redirect_response=False,
        )


class LogoutNavigationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="logout-nav@example.com",
            password="pass",
            role=ROLE_STUDENT,
        )
        self.client.force_login(self.user)

    def test_custom_logout_get_returns_405(self):
        response = self.client.get(reverse("custom-logout"))

        self.assertEqual(response.status_code, 405)

    def test_custom_logout_post_redirects_to_student_login(self):
        response = self.client.post(reverse("custom-logout"))

        self.assertRedirects(
            response,
            reverse("student:login"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)
