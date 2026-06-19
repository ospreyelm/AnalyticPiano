from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, ROLE_TEACHER, ROLE_STUDENT

class TeacherAccessMiddlewareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(email="teacher@example.com", password="pass", role=ROLE_TEACHER)
        self.student = User.objects.create_user(email="student@example.com", password="pass", role=ROLE_STUDENT)
        self.superuser = User.objects.create_superuser(email="super@example.com", password="pass")
        self.course_list_url = reverse("teacher:course-list")
        self.course_create_url = reverse("teacher:course-create")

    def test_anonymous_user_passes_through(self):
        # Anonymous users should pass through the middleware and get handled by standard decorators
        # which usually redirect them to login page.
        resp = self.client.get(self.course_list_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("accounts/login", resp.url)

    def test_student_get_redirected_to_student_home(self):
        self.client.force_login(self.student)
        resp = self.client.get(self.course_list_url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("student:home"))

    def test_student_post_returns_403_json(self):
        self.client.force_login(self.student)
        resp = self.client.post(self.course_create_url, data={}, content_type="application/json")
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertEqual(data["error"], "Permission denied.")
        self.assertEqual(data["redirectUrl"], reverse("student:home"))

    def test_teacher_get_allowed(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(self.course_list_url)
        self.assertEqual(resp.status_code, 200)

    def test_superuser_get_allowed(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(self.course_list_url)
        self.assertEqual(resp.status_code, 200)
