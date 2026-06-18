from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
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

    def test_play_view_loads_scoped_teacher_and_canvas_css(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, "student/exercise-canvas.css")
        self.assertContains(resp, "teacher/teacher-play.css")
        self.assertNotContains(resp, "student/player-canvas.css")

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

    def test_play_view_uses_workspace_main_class(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'class="t-main t-main--workspace"')
        self.assertContains(resp, 'class="t-play-workspace js-fade-in fade"')

    def test_play_view_does_not_render_legacy_lab_header_menu(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertNotContains(resp, "Dashboard")
        self.assertNotContains(resp, "New Play View")
        self.assertNotContains(resp, "DISPLAY OPTIONS")
        self.assertNotContains(resp, "_header_music.html")

    def test_play_view_preserves_required_legacy_mount_points(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'id="mainmenu"')
        self.assertContains(resp, 'class="js-keysignature-widget"')
        self.assertContains(resp, 'class="js-notation-opts-widget"')
        self.assertContains(resp, 'class="js-keyboardsize settings-inline"')
        self.assertContains(resp, 'class="js-octaveadjustment settings-inline"')
        self.assertContains(resp, 'class="js-keyboardshortcuts settings-inline"')

    def test_play_view_toolbar_preserves_js_hooks(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'js-btn-upload-json')
        self.assertContains(resp, 'js-btn-pristine')
        self.assertContains(resp, 'js-btn-import-musicxml')
        self.assertContains(resp, 'id="musicxml-upload-input"')
        self.assertContains(resp, 'id="play-meter-select"')

    def test_play_view_audio_controls_preserve_js_hooks(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'id="mute-toggle"')
        self.assertContains(resp, 'id="volume"')
        self.assertContains(resp, 'id="midi-switch"')

    def test_play_view_save_panel_uses_t_classes(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 't-card-title')
        self.assertContains(resp, 't-btn t-btn-primary')

    def test_play_view_save_panel_preserves_js_hooks(self):
        resp = self.client.get(reverse("lab:play"))
        self.assertContains(resp, 'id="play-save-description"')
        self.assertContains(resp, 'id="play-save-submit"')
        self.assertContains(resp, 'id="play-save-create-transpositions"')
        self.assertContains(resp, 'name="modes"')

    def test_exercise_canvas_css_preserves_staff_and_keyboard_layout_rules(self):
        css_path = finders.find("student/exercise-canvas.css")
        self.assertIsNotNone(css_path)
        with open(css_path, encoding="utf-8") as css_file:
            css = css_file.read()

        self.assertIn("#staff {", css)
        self.assertIn("min-width: 52rem", css)
        self.assertIn("height: 390px", css)
        self.assertIn(".keyboard {", css)
        self.assertIn("position: relative", css)
        self.assertIn(".keyboard-input-mode .input-mode-toggle", css)
        self.assertIn("#piano .click-note-input", css)
        self.assertIn("#staff-toolbar .input-source-mode-toggle", css)
