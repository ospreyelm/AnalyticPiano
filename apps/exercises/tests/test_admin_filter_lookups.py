"""Tests for the ExerciseAdmin list_filter lookups.

The Mode/AnalysisType filters extract JSONB keys over the full exercises
table on every change_list render. With ~68k rows and no index, each
lookup scanned ~437MB of JSONB (~16s). The fix moves DISTINCT into the DB
(returns ~handful of values, not 68k rows) and adds expression indexes.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.admin import (
    AnalysisTypeFilter,
    ExerciseAdmin,
    ModeFilter,
    _distinct_json_text_values,
)
from apps.exercises.models import Exercise

User = get_user_model()


def _make_exercise(*, _id, mode=None, analysis_type=None, author):
    data = {"isUMTO": True}
    if mode is not None:
        data["mode"] = mode
    if analysis_type is not None:
        data["analysisType"] = analysis_type
    return Exercise.objects.create(
        _id=_id,
        description=f"ex {_id}",
        data=data,
        authored_by=author,
        is_public=True,
        skill_tags=["unit:1"],
    )


class _FakeRequest:
    pass


class ModeFilterLookupTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="t@example.com", password="pw")
        self.admin = ExerciseAdmin(Exercise, None)
        self.req = _FakeRequest()
        _make_exercise(_id=60001, mode="roman", author=self.author)
        _make_exercise(_id=60002, mode="roman", author=self.author)  # dup
        _make_exercise(_id=60003, mode="chordal", author=self.author)
        _make_exercise(_id=60004, mode=None, author=self.author)  # no mode -> excluded

    def test_lookups_returns_distinct_sorted_values(self):
        f = ModeFilter(self.req, {}, {}, self.admin)
        self.assertEqual(f.lookups(self.req, self.admin), [("chordal", "chordal"), ("roman", "roman")])

    def test_lookups_queryset_uses_db_distinct(self):
        # The perf bug pulled all 68k rows into a Python set. DISTINCT must be
        # pushed into the DB so only the handful of distinct values ship over.
        qs = _distinct_json_text_values(self.admin.get_queryset(self.req), "mode")
        # _distinct_json_text_values returns a realized list; rebuild the
        # queryset shape to assert DISTINCT is in the emitted SQL.
        from django.db.models.fields.json import KT

        sql_qs = (
            self.admin.get_queryset(self.req)
            .annotate(_json_text=KT("data__mode"))
            .exclude(_json_text__isnull=True)
            .values_list("_json_text", flat=True)
            .distinct()
        )
        self.assertIn("DISTINCT", str(sql_qs.query).upper())


class AnalysisTypeFilterLookupTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="t@example.com", password="pw")
        self.admin = ExerciseAdmin(Exercise, None)
        self.req = _FakeRequest()
        _make_exercise(_id=61001, analysis_type="roman", author=self.author)
        _make_exercise(_id=61002, analysis_type="roman", author=self.author)  # dup
        _make_exercise(_id=61003, analysis_type="figured_bass", author=self.author)

    def test_lookups_returns_distinct_sorted_values(self):
        f = AnalysisTypeFilter(self.req, {}, {}, self.admin)
        self.assertEqual(
            f.lookups(self.req, self.admin),
            [("figured_bass", "figured_bass"), ("roman", "roman")],
        )

    def test_lookups_queryset_uses_db_distinct(self):
        from django.db.models.fields.json import KT

        qs = (
            self.admin.get_queryset(self.req)
            .annotate(_json_text=KT("data__analysisType"))
            .exclude(_json_text__isnull=True)
            .values_list("_json_text", flat=True)
            .distinct()
        )
        self.assertIn("DISTINCT", str(qs.query).upper())


class ModeFilterLookupCachingTests(TestCase):
    """The lookup enumerates a tiny, rarely-changing set of values; caching it
    means the ~8s DB scan runs once per TTL window, not on every change_list."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.cache = cache
        self.author = User.objects.create_user(email="t@example.com", password="pw")
        self.admin = ExerciseAdmin(Exercise, None)
        self.req = _FakeRequest()
        _make_exercise(_id=62001, mode="roman", author=self.author)
        _make_exercise(_id=62002, mode="chordal", author=self.author)

    def tearDown(self):
        self.cache.clear()

    def test_second_lookup_call_hits_cache_no_db_queries(self):
        from django.db import connection, reset_queries
        f = ModeFilter(self.req, {}, {}, self.admin)
        f.lookups(self.req, self.admin)  # populate cache
        reset_queries()
        f.lookups(self.req, self.admin)  # should be a cache hit
        self.assertEqual(len(connection.queries), 0)

    def test_exercise_save_busts_cache_so_new_mode_surfaces(self):
        f = ModeFilter(self.req, {}, {}, self.admin)
        self.assertEqual(f.lookups(self.req, self.admin),
                         [("chordal", "chordal"), ("roman", "roman")])
        # Author a new mode; the post_save signal must invalidate the cache.
        _make_exercise(_id=62003, mode="ear_training", author=self.author)
        self.assertEqual(
            f.lookups(self.req, self.admin),
            [("chordal", "chordal"), ("ear_training", "ear_training"), ("roman", "roman")],
        )