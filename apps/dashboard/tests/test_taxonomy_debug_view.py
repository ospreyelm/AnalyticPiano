from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class TaxonomyDebugViewTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="taxonomy-staff@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            email="taxonomy-student@test.com",
            password="testpass123",
            is_staff=False,
        )

    def test_requires_login(self):
        response = self.client.get(reverse("dashboard:taxonomy-debug"))

        self.assertEqual(response.status_code, 302)

    def test_non_staff_is_redirected_to_dashboard_home(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("dashboard:taxonomy-debug"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dashboard:index"))

    def test_staff_can_view_human_readable_taxonomy_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("dashboard:taxonomy-debug"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/taxonomy_debug.html")
        self.assertContains(response, "Curriculum Taxonomy")
        self.assertContains(response, "Standard Sequence")
        self.assertContains(response, "Branch A")
        self.assertContains(response, "Unit 9")
        self.assertContains(response, "Tonic &amp; dominant")
