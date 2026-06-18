from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ROLE_STUDENT, ROLE_TEACHER


class LoginRedirectTests(TestCase):
    password = "test-password"

    def _login(self, user):
        return self.client.post(
            reverse("custom-login"),
            {"email": user.email, "password": self.password},
        )

    def test_teacher_login_redirects_to_teacher_courses(self):
        teacher = get_user_model().objects.create_user(
            email="teacher@example.com",
            password=self.password,
            role=ROLE_TEACHER,
        )

        response = self._login(teacher)

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )

    def test_superuser_login_redirects_to_teacher_courses(self):
        superuser = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password=self.password,
        )

        response = self._login(superuser)

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )

    def test_student_role_keeps_existing_my_work_redirect(self):
        student = get_user_model().objects.create_user(
            email="student@example.com",
            password=self.password,
            role=ROLE_STUDENT,
        )

        response = self._login(student)

        self.assertRedirects(
            response,
            reverse("dashboard:my-work"),
            fetch_redirect_response=False,
        )
