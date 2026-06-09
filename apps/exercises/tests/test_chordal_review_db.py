import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class ReviewEndpointRhythmTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="r@example.com", password="x")
        self.client.force_login(self.user)
        chords = [{"offset": float(i), "duration": 1.0, "visible": [60]} for i in range(8)]
        self.ex = save_chordal_umto_exercise(
            description="t", author=self.user, chords=chords,
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0], analysis=[])

    def _url(self, ex=None):
        return f"/dashboard/api/workbench/chordal-analysis/{(ex or self.ex).id}/"

    def test_post_updates_meter_and_barlines_when_valid(self):
        body = {"meter": "2/4", "barline_offsets": [2.0, 4.0, 6.0], "rows": []}
        resp = self.client.post(self._url(), data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200, resp.content
        self.ex.refresh_from_db()
        md = self.ex.data["score"]["umto"]["metadata"]
        assert md["meter"] == "2/4"
        assert md["barline_offsets"] == [2.0, 4.0, 6.0]

    def test_post_rejects_off_palette_duration(self):
        body = {"rows": [{"offset": 0.0, "duration": 1.25}]}
        resp = self.client.post(self._url(), data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 400
        assert "palette" in resp.json()["error"].lower()

    def test_post_rejects_invalid_metered_bars(self):
        body = {"meter": "4/4", "barline_offsets": [3.0], "rows": []}
        resp = self.client.post(self._url(), data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 400

    def _with_analysis(self):
        chords = [{"offset": float(i), "duration": 1.0, "visible": [60]} for i in range(8)]
        analysis = [{"offset": 0.0, "content": {"roman_numeral": "I"},
                     "unit_tags": [], "is_target": True}]
        return save_chordal_umto_exercise(
            description="t", author=self.user, chords=chords,
            key="C major", meter="4/4", clef="keyboard",
            staff_distribution="keyboard", barline_offsets=[4.0], analysis=analysis)

    def test_meter_only_update_preserves_analysis(self):
        ex = self._with_analysis()
        body = {"meter": "2/4", "barline_offsets": [2.0, 4.0, 6.0], "rows": []}
        resp = self.client.post(self._url(ex), data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200, resp.content
        ex.refresh_from_db()
        analysis = ex.data["score"]["umto"]["analysis"]
        assert any(a["content"].get("roman_numeral") == "I" for a in analysis)

    def test_duration_only_update_preserves_analysis(self):
        ex = self._with_analysis()
        body = {"rows": [{"offset": 0.0, "duration": 1.0}]}
        resp = self.client.post(self._url(ex), data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200, resp.content
        ex.refresh_from_db()
        analysis = ex.data["score"]["umto"]["analysis"]
        assert any(a["content"].get("roman_numeral") == "I" for a in analysis)

    def test_post_rebuilds_score_measures(self):
        ex = self._with_analysis()
        body = {"meter": "2/4", "barline_offsets": [2.0, 4.0, 6.0], "rows": []}
        resp = self.client.post(self._url(ex), data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200, resp.content
        ex.refresh_from_db()
        assert len(ex.data["score"]["measures"]) == 4
        assert ex.data["score"]["meta"]["time"] == "2/4"
