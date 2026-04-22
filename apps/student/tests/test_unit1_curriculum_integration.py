from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse


User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class Unit1CurriculumIntegrationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=36001,
            email="unit1-integration-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.client.force_login(self.student)

    def test_unit1_page_shows_all_skill_lanes(self):
        response = self.client.get(reverse("student:unit", kwargs={"unit_num": 1}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Note Names")
        self.assertContains(response, "Ledger Lines")
        self.assertContains(response, "Clefs")
        self.assertContains(response, "Enharmonics")
