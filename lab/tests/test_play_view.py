from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class PlayViewTeacherChromeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="play@example.com", password="x")
        self.client.force_login(self.user)

    def test_play_view_returns_200(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertEqual(resp.status_code, 200)

    def test_play_view_uses_teacher_chrome(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 't-header')
        self.assertContains(resp, 'Monteverdi')

    def test_play_view_loads_player_canvas_css(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "student/player-canvas.css")

    def test_play_view_boots_requirejs(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "require.js")
        self.assertContains(resp, "require(['app/main']);")

    def test_play_view_does_not_load_harmony_css(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertNotContains(resp, "css/harmony.css")

    def test_play_view_loads_notation_fonts(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "Sebastian-FigBass-Modified.woff")
