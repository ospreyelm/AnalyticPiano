import re
from collections import OrderedDict
from datetime import timedelta, date, datetime
from itertools import product

from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import JSONField
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models, connections
from django.db.models import When, Case, Q, F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch
from django.utils import dateformat
from django.utils.dateparse import parse_datetime
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.safestring import mark_safe
from django_better_admin_arrayfield.models.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex

from apps.accounts.models import Group
from apps.exercises.constants import (
    SIGNATURE_CHOICES,
    KEY_SIGNATURES,
    pseudo_key_to_sig,
)
from apps.exercises.utils.recurrence import rebuild_period_progress
from apps.exercises.utils.transpose import transpose
from apps.exercises.utils.abc_preview import generate_abc_preview

User = get_user_model()


FEEDBACK_MODE_CHOICES = [
    ("submit", "Submit — see results after submitting"),
    ("practice", "Practice — immediate feedback per slot"),
    ("test", "Test — no feedback, answers locked"),
]


class RawJSONField(JSONField):
    """To preserve the data order."""

    def db_type(self, connection):
        return "json"

    def from_db_value(self, value, expression, connection):
        # Some Postgres drivers already deserialize json/jsonb columns to Python
        # objects before Django's JSONField conversion runs.
        if value is None or isinstance(value, (dict, list, bool, int, float)):
            return value
        return super().from_db_value(value, expression, connection)


class BaseContentModel(models.Model):
    _id = models.AutoField("_ID", unique=True, primary_key=True)

    class Meta:
        abstract = True

    def set_id(self, initial):
        assert len(initial) == 1

        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        reverse_id = ""
        bases = [26, 26, 10, 10, 26]
        _id = self._id
        for base in bases:
            if base == 26:
                reverse_id += letters[_id % base]
            elif base == 10:
                reverse_id += str(_id % base)
            _id //= base
        if _id != 0 or len(reverse_id) != len(bases):
            return None
        reverse_id += initial
        self.id = reverse_id[::-1]

    def full_clean(self, exclude=None, validate_unique=True):
        super(BaseContentModel, self).full_clean(
            exclude=["id", "_id", "authored_by"], validate_unique=validate_unique
        )


class ClonableModelMixin:
    @classmethod
    def get_unique_fields(cls):
        fields = []
        for field in cls._meta.fields:
            if field.unique:
                fields.append(field.name)
        return fields


class NonUMTOExerciseError(ValueError):
    """Raised when save_umto_exercise is handed legacy-shaped data, or when
    Exercise.save() / Exercise.clean() sees a new row whose data fails UMTO
    validation."""


class Exercise(ClonableModelMixin, BaseContentModel):
    id = models.CharField("E-ID", unique=True, max_length=16, null=True)
    description = models.CharField(
        "Description",
        max_length=60,
        blank=True,
        null=True,
        # help_text="Brief description",
    )
    data = RawJSONField("Data")
    rhythm = models.CharField(
        "Rhythm",
        max_length=255,
        blank=True,
        null=True,
        help_text="Duration of each chord: w h q or 1 2 4 for whole, half, quarter; W H Q for dotted whole, half, quarter respectively.",
    )
    time_signature = models.CharField(
        "Meter",
        max_length=8,
        blank=True,
        null=True,
        default="",
        help_text="Enter a numerical time signature: two numbers separated by a slash",
    )
    authored_by = models.ForeignKey(
        "accounts.User",
        related_name="exercises",
        on_delete=models.PROTECT,
        verbose_name="Author",
    )
    is_public = models.BooleanField(
        "Commons",
        default=False,
        help_text="Check to share your exercise with other users of this site: allow them to include the exercise in their playlists and see your email address.",
    )
    is_official = models.BooleanField(default=False, db_index=True)
    REVIEW_NONE = "none"
    REVIEW_PENDING = "pending"
    REVIEW_APPROVED = "approved"
    REVIEW_REJECTED = "rejected"
    REVIEW_STATUS_CHOICES = [
        (REVIEW_NONE, "none"),
        (REVIEW_PENDING, "pending"),
        (REVIEW_APPROVED, "approved"),
        (REVIEW_REJECTED, "rejected"),
    ]
    official_review_status = models.CharField(
        max_length=16,
        choices=REVIEW_STATUS_CHOICES,
        default=REVIEW_NONE,
        db_index=True,
    )

    locked = models.BooleanField("Locked", default=False)

    tags = ArrayField(
        base_field=models.CharField(max_length=32),
        default=list,
        blank=True,
        verbose_name="Tags",
    )

    skill_tags = ArrayField(
        base_field=models.CharField(max_length=64),
        default=list,
        blank=True,
        verbose_name="Skill Tags",
        help_text="Knowledge Graph skills detected in the chunk (e.g. Secondary_Dominant)"
    )

    complexity = models.PositiveSmallIntegerField(
        default=1,
        help_text="Calculated integer 1-10 representing harmony complexity"
    )

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    zero_padding = "EA00A0"

    ANALYSIS_MODE_CHOICES = (
        # not good that this is hard coded, where is this used currently?
        ("note_names", "Note Names"),
        ("scientific_pitch", "Scientific Pitch"),
        ("scale_degrees", "Scale Degrees"),
        ("solfege", "Solfege"),
        ("spacing", "Spacing of Upper Voices"),
        ("roman_numerals", "Roman Numerals"),
        ("intervals", "Intervals"),
        ("intervals_wrap_after_octave", "Intervals (Wrap After Octave)"),
        (
            "intervals_wrap_after_octave_plus_ditone",
            "Intervals (Wrap After Octave Plus Ditone)",
        ),
        ("generic_intervals", "Generic Intervals"),
        (
            "generic_intervals_wrap_after_octave",
            "Generic Intervals (Wrap After Octave)",
        ),
        (
            "generic_intervals_wrap_after_octave_plus_ditone",
            "Generic Intervals (Wrap After Octave Plus Ditone)",
        ),
    )

    HIGHLIGHT_MODE_CHOICES = (
        ("roothighlight", "Root Highlight"),
        ("tritonehighlight", "Tritone Highlight"),
    )

    class Meta:
        verbose_name = "Exercise"
        verbose_name_plural = "Exercises"
        indexes = [
            GinIndex(fields=['skill_tags']),
            models.Index(fields=['complexity']),
        ]

    @classmethod
    def get_data_order_list(cls):
        return [
            "type",
            "introText",
            "reviewText",
            "staffDistribution",
            "key",
            "keySignature",
            "analysis",
            "highlight",
            "chord",
            "timeSignature",
            "semibrevesPerLine",
        ]

    @property
    def is_private(self):
        return not self.is_public

    def __str__(self):
        return self.id

    def clean(self):
        """
        Enforce UMTO schema for all new or updated exercises.
        Can be bypassed via HARMONYLAB_ALLOW_LEGACY_EXERCISE=1 for migrations.
        """
        import os
        super().clean()
        
        # Only enforce on new rows. Existing rows are grandfathered.
        if self._id is not None:
            return

        # Bypass for migrations
        if os.environ.get("HARMONYLAB_ALLOW_LEGACY_EXERCISE") == "1":
            return

        # Block non-UMTO data
        if not self.data or not self.data.get("isUMTO"):
            raise NonUMTOExerciseError(
                "Legacy exercise schema is no longer allowed. "
                "Exercises must be created/updated via the UMTO factory (save_umto_exercise)."
            )

    def get_previous_authored_exercise(self):
        return Exercise.objects.filter(
            authored_by=self.authored_by, created__lt=self.created
        ).last()

    def get_next_authored_exercise(self):
        return Exercise.objects.filter(
            authored_by=self.authored_by, created__gt=self.created
        ).first()

    def save(self, *args, **kwargs):
        self.clean()
        skip_auto_playlist = kwargs.pop("skip_auto_playlist", False)
        if not self._id:
            super(Exercise, self).save(*args, **kwargs)
            self.set_id(initial="E")
            self.sort_data()
            self.set_rhythm_values()
            update_kwargs = kwargs.copy()
            update_kwargs.pop("force_insert", None)
            super(Exercise, self).save(*args, **update_kwargs)
            if not skip_auto_playlist:
                self.set_auto_playlist()
            return

        # self.validate_unique()
        if not self.id:
            # Derivation from _id is deterministic, so recomputing is a no-op for
            # normal rows — but rows imported with a preserved cross-environment id
            # (import_factory_curated) must keep it across subsequent saves.
            self.set_id(initial="E")
        self.sort_data()
        self.set_rhythm_values()

        super(Exercise, self).save(*args, **kwargs)

    def sort_data(self):
        if not all([key in self.data for key in self.get_data_order_list()]):
            return

        index_map = {v: i for i, v in enumerate(self.get_data_order_list())}
        self.data = OrderedDict(
            sorted(self.data.items(), key=lambda pair: index_map[pair[0]])
        )

    def set_rhythm_values(self):
        if not self.rhythm or not self.data:
            return

        supported_rhythm_values = ["w", "W", "H", "h", "Q", "q", "1", "2", "4"]
        rhythm_values = (
            self.rhythm.replace("1", "w").replace("2", "h").replace("4", "q")
        )
        rhythm_values = [x for x in rhythm_values if x in supported_rhythm_values]
        chord_data = self.data.get("chord")
        del rhythm_values[len(chord_data) :]  # truncate extra rhythms
        if len(rhythm_values) > 0 and len(rhythm_values) < len(chord_data):
            rhythm_values.append("w" * (len(chord_data) - len(rhythm_values)))
        self.rhythm = " ".join(rhythm_values)

        for chord in chord_data:
            try:
                chord.update(rhythmValue=rhythm_values.pop(0))
            except IndexError:
                break
        self.data["chord"] = chord_data

    def set_auto_playlist(self):
        auto_playlist = Playlist.objects.filter(
            authored_by=self.authored_by,
            is_auto=True,
            updated__gt=now()
            - timedelta(hours=8),  # capture playlists authored in the last eight hours
        ).last()
        if auto_playlist is None:
            auto_playlist = Playlist.create_auto_playlist(
                authored_by=self.authored_by, initial_exercise_id=self.id
            )
        lately_edited_playlists = Playlist.objects.filter(
            updated__gt=auto_playlist.updated
        )
        if lately_edited_playlists.exists():
            Playlist.create_auto_playlist(
                authored_by=self.authored_by, initial_exercise_id=self.id
            )
            return
        auto_playlist.append_exercise(self.id)

    @cached_property
    def has_been_performed(self):
        return self.locked

        # author = self.authored_by
        # performed_exercises = []
        # for x in list(PerformanceData.objects.exclude(user=self.authored_by).values_list('data', flat=True)):
        #     for y in x:
        #         performed_exercises.append(y['id'][:6])  ## because of transposed exercises
        # performed_exercises = set(performed_exercises)
        # return self.id in performed_exercises

        # return PerformanceData.objects.filter(
        #     data__contains=[{'id': self.id}]
        # ).exclude(user=self.authored_by).exists()

    @property
    def lab_url(self):
        return reverse("lab:exercise-view", kwargs={"exercise_id": self.id})

    def set_data_modes(self, field_name, modes, enabled):
        if field_name not in self.data:
            return

        _data = self.data.get(field_name)
        for mode in _data["mode"]:
            if modes and mode in modes:
                _data["mode"][mode] = True
            elif not modes or mode not in modes:
                _data["mode"][mode] = False

        self.data[field_name] = _data
        self.data[field_name]["enabled"] = enabled
        return self

    def lock(self):
        self.locked = True
        self.save()

    @property
    def preview_notation(self):
        return generate_abc_preview(self)


class StudentSkillMastery(models.Model):
    """
    Tracks a single student's mastery level for a single skill tag.
    One row per (user, skill_tag) pair.
    """
    LEVEL_NOT_STARTED = "not_started"
    LEVEL_ATTEMPTED   = "attempted"
    LEVEL_FAMILIAR    = "familiar"
    LEVEL_PROFICIENT  = "proficient"
    LEVEL_MASTERED    = "mastered"
    LEVEL_CHOICES = [
        (LEVEL_NOT_STARTED, "Not Started"),
        (LEVEL_ATTEMPTED,   "Attempted"),
        (LEVEL_FAMILIAR,    "Familiar"),
        (LEVEL_PROFICIENT,  "Proficient"),
        (LEVEL_MASTERED,    "Mastered"),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="skill_masteries")
    skill_tag  = models.CharField("Skill Tag", max_length=64)

    # Mastery state
    level           = models.CharField(max_length=16, choices=LEVEL_CHOICES, default=LEVEL_NOT_STARTED)
    # Rolling boolean list of last 10 attempts (True = correct)
    recent_history  = JSONField(default=list)
    # Unique calendar date strings (YYYY-MM-DD) when the skill was practiced, capped at 30
    practice_days   = JSONField(default=list)
    total_correct   = models.PositiveIntegerField(default=0)
    total_attempts  = models.PositiveIntegerField(default=0)

    # Timestamps
    last_practiced  = models.DateTimeField(null=True, blank=True)
    mastered_at     = models.DateTimeField(null=True, blank=True)
    first_attempted = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Student Skill Mastery"
        verbose_name_plural = "Student Skill Masteries"
        unique_together = ("user", "skill_tag")
        indexes = [
            models.Index(fields=["user", "level"]),
            models.Index(fields=["user", "last_practiced"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.skill_tag}: {self.level}"


class SkillPrerequisite(models.Model):
    """
    A directed edge in the skill prerequisite DAG.
    course=None means a global default; a course FK means a teacher override for that course.
    """
    course       = models.ForeignKey(
        "Course",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="skill_prerequisites",
        help_text="Leave blank for global default DAG. Set to a course for course-specific overrides.",
    )
    skill_tag    = models.CharField("Skill Tag", max_length=64,
                                    help_text="The skill that requires the prerequisite.")
    requires_tag = models.CharField("Requires Tag", max_length=64,
                                    help_text="The skill that must be acquired first.")

    class Meta:
        verbose_name = "Skill Prerequisite"
        verbose_name_plural = "Skill Prerequisites"
        unique_together = ("course", "skill_tag", "requires_tag")

    def __str__(self):
        course_label = self.course.id if self.course else "global"
        return f"[{course_label}] {self.skill_tag} ← {self.requires_tag}"


class IdentificationAttempt(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="identification_attempts"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name="identification_attempts"
    )
    course = models.ForeignKey(
        "Course", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="identification_attempts"
    )
    playlist = models.ForeignKey(
        "Playlist", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="identification_attempts"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    answers = JSONField(default=dict)
    correctness = JSONField(default=dict)
    score = JSONField(default=dict)
    correct_answers = JSONField(default=dict)
    is_page_submit = models.BooleanField(default=False)
    page_num = models.IntegerField(null=True, blank=True)
    mode = models.CharField(
        "Feedback Mode",
        max_length=16,
        choices=FEEDBACK_MODE_CHOICES,
        blank=True,
        default="",
        help_text="Mode in effect when this attempt was submitted. "
                  "Empty = pre-migration attempt (mode unknown).",
    )
    ATTEMPT_PRACTICE = "practice"
    ATTEMPT_MASTERY_CHALLENGE = "mastery_challenge"
    ATTEMPT_TYPE_CHOICES = [
        (ATTEMPT_PRACTICE, "Practice"),
        (ATTEMPT_MASTERY_CHALLENGE, "Mastery Challenge"),
    ]
    attempt_type = models.CharField(
        "Attempt Type",
        max_length=32,
        choices=ATTEMPT_TYPE_CHOICES,
        default=ATTEMPT_PRACTICE,
    )

    class Meta:
        verbose_name = "Identification Attempt"
        verbose_name_plural = "Identification Attempts"
        ordering = ["submitted_at"]

    def __str__(self):
        return f"User:{self.user} Exercise:{self.exercise_id} at {self.submitted_at}"


@receiver(models.signals.post_delete, sender=Exercise)
def remove_exercise_from_playlists(sender, instance, *args, **kwargs):
    """
    Remove the deleted exercise from all playlists that contain it
    """
    Playlist.remove_exercise_from_playlists(exercise_id=instance._id)


class Playlist(ClonableModelMixin, BaseContentModel):
    id = models.CharField("P-ID", unique=True, max_length=16, null=True)
    FAMILY_TEACHER_PLAY = "teacher_play"
    PLAYLIST_FAMILY_CHOICES = (
        ("", "Unclassified"),
        (FAMILY_TEACHER_PLAY, "Teacher Play authored exercises"),
    )
    is_auto = models.BooleanField(
        "Auto-generated",
        default=False,
        help_text="This box is checked if AnalyticPiano generated the playlist from your newly created exercises and you made no edits.",
    )

    name = models.CharField(
        "Name",
        max_length=64,
    )
    authored_by = models.ForeignKey(
        "accounts.User",
        related_name="playlists",
        on_delete=models.PROTECT,
        verbose_name="Author of Playlist",
    )
    playlist_family = models.CharField(
        max_length=24,
        choices=PLAYLIST_FAMILY_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    canonical_unit = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    canonical_mode = models.CharField(
        max_length=20,
        blank=True,
        default="",
        db_index=True,
    )

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    # exercises = models.CharField(
    #     "Exercise IDs",
    #     max_length=1024,
    #     # help_text='Ordered set of exercise IDs, separated by comma, semicolon, space, or newline.'
    # )

    exercises = models.ManyToManyField(
        to=Exercise,
        related_name="playlists",
        through="ExercisePlaylistOrdered",
        # help_text="The exercises in the playlist.",
        blank=True,
    )

    transpose_requests = ArrayField(
        base_field=models.CharField(max_length=10, choices=SIGNATURE_CHOICES),
        default=list,
        blank=True,
        null=True,
        help_text=f'Valid choices are {" ".join(str(x) for x in KEY_SIGNATURES)}',
        verbose_name="Transpose requests",
    )

    TRANSPOSE_OFF = None
    TRANSPOSE_EXERCISE_LOOP = "Exercise Loop"
    TRANSPOSE_PLAYLIST_LOOP = "Playlist Loop"
    TRANSPOSE_EXERCISE_SHUFFLE = "Exercise Shuffle"
    TRANSPOSE_PLAYLIST_SHUFFLE = "Playlist Shuffle"
    TRANSPOSE_TYPE_CHOICES = (
        (TRANSPOSE_OFF, "No transposition"),
        (TRANSPOSE_EXERCISE_LOOP, "Loop all keys for each exercise"),
        (TRANSPOSE_PLAYLIST_LOOP, "Loop all exercises for each key"),
        # (TRANSPOSE_EXERCISE_SHUFFLE, TRANSPOSE_EXERCISE_SHUFFLE),
        # (TRANSPOSE_PLAYLIST_SHUFFLE, TRANSPOSE_PLAYLIST_SHUFFLE),
    )
    transposition_type = models.CharField(
        "Transposition Types",
        max_length=32,
        choices=TRANSPOSE_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="Apply transposition operations to the list of exercises.",
    )
    is_public = models.BooleanField(
        "Commons",
        default=False,
        help_text="Sharing your playlist will allow other users to include it in their courses. Doing so will reveal your email address to all users of the site.",
    )
    is_official = models.BooleanField(default=False, db_index=True)
    official_review_status = models.CharField(
        max_length=16,
        choices=Exercise.REVIEW_STATUS_CHOICES,
        default=Exercise.REVIEW_NONE,
        db_index=True,
    )
    is_adaptive = models.BooleanField(
        "Adaptive Mode",
        default=False,
        help_text="In adaptive mode, the next exercise is chosen dynamically based on student mastery.",
    )
    is_dynamic = models.BooleanField(
        "Smart Assignment",
        default=False,
        help_text="If checked, this playlist will automatically pull exercises from the global library based on targeted tags and complexity, rather than a manual list.",
    )
    min_complexity = models.PositiveSmallIntegerField(
        "Min Complexity",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Filter the pool to exercises with complexity at or above this value (1-10)."
    )
    max_complexity = models.PositiveSmallIntegerField(
        "Max Complexity",
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Filter the pool to exercises with complexity at or below this value (1-10)."
    )

    tags = ArrayField(
        base_field=models.CharField(max_length=32),
        default=list,
        blank=True,
        verbose_name="Tags",
    )

    skill_tags = ArrayField(
        base_field=models.CharField(max_length=64),
        default=list,
        blank=True,
        verbose_name="Skill Tags",
        help_text="Harmonic skills this playlist targets (e.g. Dominant_Seventh). "
                  "Used to filter identification slots in chorale exercises."
    )

    feedback_mode = models.CharField(
        "Feedback Mode Override",
        max_length=16,
        choices=FEEDBACK_MODE_CHOICES,
        blank=True,
        default="",
        help_text="Overrides exercise identMode for all exercises in this playlist. "
                  "Leave blank to use each exercise's own setting.",
    )

    zero_padding = "PA00A0"

    class Meta:
        verbose_name = "Playlist"
        verbose_name_plural = "Playlists"
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~Q(playlist_family="teacher_play")
                    | (Q(canonical_unit__isnull=False) & ~Q(canonical_mode=""))
                ),
                name="teacher_play_requires_unit_and_mode",
            ),
            models.UniqueConstraint(
                fields=[
                    "authored_by",
                    "playlist_family",
                    "canonical_unit",
                    "canonical_mode",
                ],
                condition=Q(playlist_family="teacher_play"),
                name="uniq_teacher_play_author_unit_mode",
            )
        ]

    @cached_property
    def untransposed_exercises_ids(self):
        return list(
            ExercisePlaylistOrdered.objects.filter(playlist=self)
            .order_by("order")
            .values_list("exercise__id", flat=True)
        )

    def prime_untransposed_exercises_ids(self, exercise_ids):
        """Seed the untransposed_exercises_ids cached_property without a query.

        Callers MUST pass exactly what the property would compute: the list of
        string exercise ids ordered by ExercisePlaylistOrdered.order. Used by
        batch-fetch paths (see apps.student.unit_progress._batch_playlist_data)
        to avoid a per-playlist query.
        """
        self.__dict__["untransposed_exercises_ids"] = list(exercise_ids)

    @property
    def exercise_list(self):
        if not self.is_transposed():
            return self.untransposed_exercises_ids
        return self.transposed_exercises_ids

    # Returns a dict formatted <exercise_id: exercise instance>
    @property
    def exercise_dict(self):
        ex_dict = {}
        exercises = self.exercises.all()
        for exercise in exercises:
            ex_dict[exercise.id] = exercise
        return ex_dict

    @cached_property
    def exercise_count(self):
        if not self.is_transposed():
            return len(self.untransposed_exercises_ids)

        return len(self.transposed_exercises_ids)

    @cached_property
    def transposition_matrix(self):
        if not self.exercises:
            return []

        sorted_exercise_list = self.untransposed_exercises_ids

        parsed_staff_sigs = []
        for i in range(0, len(self.transpose_requests)):
            try:
                staff_sig = pseudo_key_to_sig[self.transpose_requests[i]]
            except KeyError:
                staff_sig = False
            if staff_sig != False:
                parsed_staff_sigs.append(staff_sig)

        staff_sig_requests = []
        for i in range(0, len(parsed_staff_sigs)):
            parsed_staff_sig = parsed_staff_sigs[i]
            if parsed_staff_sig not in staff_sig_requests:
                staff_sig_requests.append(parsed_staff_sig)
        # ^ If an exercise is presented more than once in the same key, critical grading errors result

        if self.transposition_type == self.TRANSPOSE_EXERCISE_LOOP:
            return list(product(sorted_exercise_list, staff_sig_requests))
        elif self.transposition_type == self.TRANSPOSE_PLAYLIST_LOOP:
            return [
                (t[1], t[0]) for t in product(staff_sig_requests, sorted_exercise_list)
            ]

    @cached_property
    def transposed_exercises_ids(self):
        if not self.transposition_matrix:
            return []

        result = []
        for transposition in self.transposition_matrix:
            exercise_id, staff_sig_request = transposition
            result.append(
                transpose(self.exercise_dict[exercise_id], staff_sig_request).id
            )
        return result

    @property
    def exercise_objects(self):
        whens = []
        for sort_index, value in enumerate(self.exercise_list):
            whens.append(When(id=value, then=sort_index))

        exercises = (
            Exercise.objects.filter(id__in=self.exercise_list)
            .annotate(_sort_index=Case(*whens, output_field=models.CharField()))
            .order_by("_sort_index")
        )

        return exercises

    def append_exercise(self, exercise_id):
        # TODO: add checks to ensure order integrity
        self.exercises.add(
            Exercise.objects.get(id=exercise_id),
            through_defaults={"order": len(self.exercises.all()) + 1},
        )
        self.save()

    def is_transposed(self):
        return self.transpose_requests and self.transposition_type

    def get_exercise_obj_by_num(self, num=1):
        if len(self.exercise_list) == 0 or num == None:
            return
        try:
            exercise = Exercise.objects.filter(id=self.exercise_list[num - 1]).first()
        except (IndexError, TypeError):
            exercise = Exercise.objects.filter(id=self.exercise_list[-1]).first()

        if not self.is_transposed():
            return exercise

        # import pdb; pdb.set_trace()
        exercise_id, staff_sig_request = self.transposition_matrix[num - 1]
        exercise = Exercise.objects.get(id=exercise_id)
        transposed_exercise = transpose(exercise, staff_sig_request)
        # import pdb; pdb.set_trace()
        return transposed_exercise

    def get_exercise_url_by_num(
        self,
        num=1,
        course_id=None,
    ):
        if num == None or num > self.exercise_count:
            return None
        try:
            return reverse(
                "lab:playlist-view",
                kwargs={
                    "playlist_id": self.id,
                    "course_id": course_id,
                    "exercise_num": num,
                },
            )
        except NoReverseMatch:
            return None

    def get_exercise_url_by_id(self, id, course_id=None):
        try:
            exercise_num = self.exercise_list.index(id) + 1
        except ValueError:
            # print ('playlist changed since this exercise performed', id, self.exercise_list);
            return None
        try:
            return reverse(
                "lab:playlist-view",
                kwargs={
                    "playlist_id": self.id,
                    "course_id": course_id,
                    "exercise_num": exercise_num,
                },
            )
        except NoReverseMatch:
            return None

    def first(self):
        if self.exercise_count > 0:
            return self.exercise_list[0]
        return None

    def last(self):
        if self.exercise_count > 0:
            return self.exercise_list[-1]
        return None

    def next_num(self, num=1):
        if num < self.exercise_count:
            return num + 1
        return None

    def prev_num(self, num=1):
        if 1 < num <= self.exercise_count:
            return num - 1
        return None

    def next(self, num=1):
        return self.get_exercise_obj_by_num(num + 1)

    def previous(self, num=1):
        return self.get_exercise_obj_by_num(num - 1)

    def __str__(self):
        return self.id

    def get_previous_authored_playlist(self):
        return Playlist.objects.filter(
            authored_by=self.authored_by, created__lt=self.created
        ).last()

    def get_next_authored_playlist(self):
        return Playlist.objects.filter(
            authored_by=self.authored_by, created__gt=self.created
        ).first()

    def save(self, *args, **kwargs):
        if not self._id:
            super(Playlist, self).save(*args, **kwargs)
        self.set_id(initial="P")
        self.set_auto_name()
        # self.clean_exercises()
        kwargs.pop("force_insert", None)
        kwargs.pop("force_update", None)
        super(Playlist, self).save(*args, **kwargs)
        return self

    # def clean_exercises(self):
    #     self.exercises = re.sub(" +", " ", self.exercises).strip()

    @cached_property
    def has_been_performed(self):
        return (
            PerformanceData.objects.filter(playlist=self)
            .filter(~Q(user=self.authored_by))
            .exists()
        )

    @classmethod
    def create_auto_playlist(cls, initial_exercise_id, authored_by):
        auto_playlist = Playlist(authored_by=authored_by, is_auto=True)
        auto_playlist.save()
        auto_playlist.exercises.add(
            Exercise.objects.get(id=initial_exercise_id),
            through_defaults={"order": 1},
        )
        auto_playlist.save()
        return auto_playlist

    @classmethod
    def remove_exercise_from_playlists(cls, exercise_id):
        ExercisePlaylistOrdered.objects.filter(exercise_id=exercise_id).delete()

    def remove_exercise(self, exercise_id):
        self.exercises = self.exercises.remove(Exercise.objects.get(id=exercise_id))
        self.save()

    def set_auto_name(self):
        if self.is_auto and not self.name:
            auto_id = list(self.id)
            auto_id[0] = "U"
            auto_id = "".join(auto_id)
            date, time = now().date().strftime("%Y%m%d"), now().time().strftime("%H%M")
            self.name = f"{auto_id}_{date}_{time}"


def get_default_data():
    return {"exercises": []}


class ExercisePlaylistOrdered(ClonableModelMixin, BaseContentModel):
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    order = models.IntegerField("Order")
    is_adaptive_entry = models.BooleanField(
        "Adaptive Entry Point",
        default=False,
        help_text="Mark as a starting exercise for students with no mastery in this adaptive playlist.",
    )
    difficulty_tier = models.PositiveSmallIntegerField(
        "Difficulty Tier",
        default=1,
        help_text="Curricular sequencing tier (e.g., 1=easy, 2=medium, 3=hard)."
    )
    is_mastery_challenge_source = models.BooleanField(
        "Mastery Challenge Source",
        default=False,
        help_text="If checked, this exercise is eligible to be drawn for a mastery challenge."
    )


    def save(self, *args, **kwargs):
        if self.order is None:
            self.order = len(
                ExercisePlaylistOrdered.objects.filter(
                    Q(exercise=self.exercise) & Q(playlist=self.playlist)
                )
            )
        super(ExercisePlaylistOrdered, self).save(*args, **kwargs)


class Course(ClonableModelMixin, BaseContentModel):
    id = models.CharField("C-ID", unique=True, max_length=16, blank=True, null=True)

    title = models.CharField(
        "Name",
        max_length=64,
    )

    open = models.BooleanField(
        "Visible to ALL",
        default=True,
        help_text="This course will be displayed to ALL your performer connections, whether or not you included them in the groups below.",
    )
    # playlists = models.CharField(
    #     'Playlist IDs',
    #     max_length=1024,
    #     # PLEASEFIX make this required=False,
    #     # help_text='Ordered set of playlist IDs, separated by comma, semicolon, space, or newline.'
    # )
    playlists = models.ManyToManyField(
        to=Playlist,
        related_name="courses",
        through="PlaylistCourseOrdered",
        blank=True,
        # help_text="The playlists in the course.",
    )

    authored_by = models.ForeignKey(
        "accounts.User",
        related_name="courses",
        on_delete=models.PROTECT,
        verbose_name="Author of Course",
    )
    is_public = models.BooleanField(
        "Commons",
        default=False,
        help_text="Sharing your course may, in future, make it available to other users for copying and editing as they wish. If so, your email address will be revealed to all users of the site.",
    )

    # publish_dates = models.CharField(
    #     "Publish Dates",
    #     max_length=1024, f
    #     blank=True,
    #     null=True,
    #     help_text="Publish date of each playlist, separated by space.",
    # )

    # due_dates = models.CharField(
    #     "Due Dates", max_length=1024, blank=True, null=True, help_text="Due date of each playlist, separated by space."
    # )

    visible_to = models.ManyToManyField(
        to=Group,
        related_name="visible_courses",
        blank=True,
        help_text="This course will ALWAYS be displayed to performer connections who are members of these groups.",
        verbose_name="User Groups",
    )

    performance_dict = JSONField(default=dict, verbose_name="Performances", blank=True)

    # Adaptive Learning settings
    adaptive_mode = models.BooleanField(
        "Adaptive Learning",
        default=False,
        help_text="Enable mastery-based adaptive engine for this course.",
    )
    required_skills = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
        verbose_name="Required Skills",
        help_text="Override the global prerequisite DAG with specific skills for this course.",
    )
    mastery_threshold = models.CharField(
        max_length=16,
        choices=StudentSkillMastery.LEVEL_CHOICES,
        default=StudentSkillMastery.LEVEL_MASTERED,
        help_text="Students must reach this level to 'complete' a skill in this course.",
    )

    start_date = models.DateField(
        "Semester Start Date",
        blank=True,
        null=True,
        help_text="Optional semester start date for the course creation wizard.",
    )
    end_date = models.DateField(
        "Semester End Date",
        blank=True,
        null=True,
        help_text="Optional semester end date for the course creation wizard.",
    )

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    timely_credit = models.DecimalField(
        "Points per playlist if timely",
        default=1.0,
        decimal_places=1,
        max_digits=4,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    tardy_credit = models.DecimalField(
        "Points per playlist if tardy",
        default=0.9,
        decimal_places=1,
        max_digits=4,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    late_credit = models.DecimalField(
        "Points per playlist if late",
        default=0.6,
        decimal_places=1,
        max_digits=4,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    tardy_threshold = models.IntegerField(
        "Late threshold (hours)",
        default=5 * 24,
        help_text="When performances are submitted after the due date, this threshold determines if they are considered tardy or late. Submissions before this threshold are tardy, submissions after are late.",
        validators=[MinValueValidator(0), MaxValueValidator(4320)],
    )

    class Meta:
        verbose_name = "Course"
        verbose_name_plural = "Courses"
        constraints = [
            # TODO: reexamine constraints and if we should enforce similar constraints of models across the project
            models.CheckConstraint(
                check=Q(tardy_credit__lte=F("timely_credit")),
                name="course_tardy_credit_lte_timely_credit",
            ),
            models.CheckConstraint(
                check=Q(late_credit__lte=F("timely_credit")),
                name="course_late_credit_lte_timely_credit",
            ),
            models.CheckConstraint(
                check=Q(late_credit__lte=F("tardy_credit")),
                name="course_late_credit_lte_tardy_credit",
            ),
        ]

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        if not self._id:
            super(Course, self).save(*args, **kwargs)
        self.set_id(initial="C")
        # Check the database to see if the tardy_threshold has changed,
        #   database call preferred to some of the other solutions talked about here: https://stackoverflow.com/questions/1355150/
        prev_course = Course.objects.filter(_id=self._id).first()
        if prev_course:
            if prev_course.tardy_threshold != self.tardy_threshold:
                self.refresh_performance_dict(commit=False)
        super(Course, self).save(*args, **kwargs)
        return self

    def clean(self):
        if self.tardy_credit > self.timely_credit:
            raise ValidationError(
                f"Tardy credit must not be greater than the timely credit"
            )
        if self.late_credit > self.tardy_credit:
            raise ValidationError(
                f"Late credit must not be greater than the tardy credit"
            )
        if self.late_credit > self.timely_credit:
            raise ValidationError(
                f"Late credit must not be greater than the timely credit"
            )

    @cached_property
    def has_been_performed(self):
        return (
            PerformanceData.objects.filter(course=self)
            .filter(~Q(user=self.authored_by))
            .exists()
        )

    @cached_property
    def playlist_id_list(self):
        return list(map(lambda p: p.id, self.playlists.all()))

    @cached_property
    def publish_dates_dict(self):
        pco_list = PlaylistCourseOrdered.objects.filter(
            course_id=self._id
        ).select_related("playlist")
        return {
            pco.playlist.id: pco.publish_date.replace(
                tzinfo=ZoneInfo(settings.TIME_ZONE)
            )
            for pco in pco_list
        }
        # publish dates are defined by course authors and should be understood in terms of their own or their institution's timezone
        # the values of pco.publish_date are NOT to be read as UTC

    @cached_property
    def due_dates_dict(self):
        pco_list = PlaylistCourseOrdered.objects.filter(
            course_id=self._id
        ).select_related("playlist")
        return {
            pco.playlist.id: pco.due_date.replace(
                tzinfo=ZoneInfo(settings.TIME_ZONE)
            )
            for pco in pco_list
        }
        # due dates are defined by course authors and should be understood in terms of their own or their institution's timezone
        # the values of pco.due_date are NOT to be read as UTC

    @cached_property
    def published_playlists(self):
        return self.playlists.all().filter(
            playlistcourseordered__publish_date__lte=date.today()
        )

    def get_due_date(self, playlist):
        due_date_of_playlist = PlaylistCourseOrdered.objects.get(
            Q(playlist_id=playlist._id, course_id=self._id)
        ).due_date
        return due_date_of_playlist.replace(tzinfo=ZoneInfo(settings.TIME_ZONE))
        # due dates are defined by course authors and should be understood in terms of their own or their institution's timezone
        # the due_date is NOT to be read as UTC

    def add_performance_to_dict(self, performance_data, commit=True):
        # Assigns numerical value to each pass mark to prevent "better" pass marks from being overwritten
        pass_marks_worst_to_best = ["X", "C", "L", "T", "P"]

        pco = PlaylistCourseOrdered.objects.get(
            course_id=self._id, playlist_id=performance_data.playlist_id
        )
        # TODO: it might be bad to rely upon str, which is liable to change, but then again we could just refresh when that happens
        performer = str(User.objects.get(id=performance_data.user_id)) # looks like e.g. "Joe Student - student@college.edu"
        pass_mark = "X"
        if performance_data.playlist_passed():
            pass_mark = "C"
            try:
                due_date = pco.due_date.replace(
                    tzinfo=ZoneInfo(settings.TIME_ZONE)
                )
            except:
                due_date = False
            try:
                pass_date = performance_data.get_local_pass_date()
            except:
                pass_date = False
                # ERROR MESSAGE SHOULD READ: 'Failed to get local_pass_date, so course activity table may not show lateness accurately.'
            if due_date and pass_date:
                if pass_date <= due_date:
                    pass_mark = "P"
                if pass_date > due_date:
                    pass_mark = "L"
                    late_diff = pass_date - due_date
                    hours = late_diff.days * 24 + late_diff.seconds // 3600
                    if hours == 0:
                        pass_mark = "P"
                        # grace period of up to one hour due to // operation above
                    elif hours < self.tardy_threshold:
                        pass_mark = "T"
                        # tardy category
        if not (performer in self.performance_dict):
            self.performance_dict[performer] = {}
        # Only overwrite previous performance if new performance is better
        if (
            pass_marks_worst_to_best.index(
                self.performance_dict.get(performer, {}).get(pco.playlist.id, "X")
            )
            <= pass_marks_worst_to_best.index(pass_mark)
        ):
            # important that the dictionary key is pco.playlist.id, not pco.order nor pco.playlist_id
            self.performance_dict[performer][pco.playlist.id] = pass_mark
        # self.performance_dict[performer].pop("reset") # UNCOMMENT TO MAINTAIN PREVIOUS INEFFICIENT LOGIC
        try:
            if not "reset" in self.performance_dict[performer]:
                self.performance_dict[performer]["reset"] = True # bug fix for pre-2024-10 data
                self.performance_dict[performer]["time_elapsed"] = 0
                for exercise_data in performance_data.data:
                    self.performance_dict[performer]["time_elapsed"] += \
                        exercise_data["performance_duration_in_seconds"]
                    print(exercise_data["performance_duration_in_seconds"])
            else:
                # self.performance_dict[performer] is the record used for the course activity table
                # it keeps track of whether each playlist has been passed and how long has been spent on each course
                # performance_data.data is the complete array of performances for the individual user
                exercise_data = performance_data.data[-1:][0]
                self.performance_dict[performer]["time_elapsed"] += \
                    exercise_data["performance_duration_in_seconds"]
                print(exercise_data["performance_duration_in_seconds"])
        except:
            pass
        if commit:
            self.save()

    def refresh_performance_dict(self, commit=True):
        self.performance_dict = {}
        course_performances = PerformanceData.objects.filter(
            Q(course=self) | Q(course=None, playlist__in=self.playlists.all())
        ).order_by("updated")
        for pd in course_performances:
            self.add_performance_to_dict(pd, commit=False)
        if commit:
            self.save()


class PlaylistCourseOrdered(ClonableModelMixin, BaseContentModel):
    RECURRENCE_UNIT_DAY = "day"
    RECURRENCE_UNIT_WEEK = "week"
    RECURRENCE_UNIT_CHOICES = (
        (RECURRENCE_UNIT_DAY, "Day"),
        (RECURRENCE_UNIT_WEEK, "Week"),
    )

    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    order = models.IntegerField("Order", help_text="Unit #")
    due_date = models.DateTimeField("Due Date", blank=True, default=None, null=True)
    publish_date = models.DateTimeField(
        "Publish Date",
        blank=True,
        default=None,
        null=True,
    )
    is_recurring = models.BooleanField(default=False)
    recurrence_unit = models.CharField(
        max_length=8,
        choices=RECURRENCE_UNIT_CHOICES,
        blank=True,
        default="",
    )
    required_passes_per_period = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    recurrence_starts_on = models.DateTimeField(blank=True, default=None, null=True)

    displayed_fields = ("due_date", "publish_date")

    def clean(self):
        super().clean()
        if self.is_recurring and not self.recurrence_unit:
            raise ValidationError(
                {"recurrence_unit": "A recurrence unit is required for recurring assignments."}
            )


class RecurringPlaylistPeriodProgress(models.Model):
    user = models.ForeignKey(
        User,
        related_name="recurring_playlist_progress",
        on_delete=models.CASCADE,
    )
    course = models.ForeignKey(
        Course,
        related_name="recurring_playlist_progress",
        on_delete=models.CASCADE,
    )
    playlist = models.ForeignKey(
        Playlist,
        related_name="recurring_playlist_progress",
        on_delete=models.CASCADE,
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    counted_passes = models.PositiveIntegerField(default=0)
    required_passes = models.PositiveIntegerField(default=1)
    target_met = models.BooleanField(default=False)
    first_pass_at = models.DateTimeField(blank=True, default=None, null=True)
    last_counted_pass_at = models.DateTimeField(blank=True, default=None, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "course", "playlist", "period_start"),)


class PerformanceData(models.Model):
    user = models.ForeignKey(
        User, related_name="performance_data", on_delete=models.PROTECT
    )
    playlist = models.ForeignKey(
        Playlist, related_name="performance_data", on_delete=models.PROTECT
    )
    course = models.ForeignKey(
        Course,
        related_name="performance_data",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    data = JSONField("Raw Data", default=list)

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    class Meta:
        verbose_name = "Performance"
        verbose_name_plural = "Performance Data"
        unique_together = (("user", "playlist", "course"),)

    def __str__(self):
        return f"Playlist:{self.playlist}, Course:{self.course} - User:{self.user}"

    @classmethod
    def get_by_user(cls, user_id: int):
        return cls.objects.filter(user_id=user_id)

    @classmethod
    def get_by_playlist(cls, playlist_id: int):
        return cls.objects.filter(playlist_id=playlist_id)

    @classmethod
    def submit(
        cls,
        user_id: int,
        course_id: int,
        playlist_id: int,
        exercise_id: str,
        data: dict,
    ):
        pd, _ = cls.objects.get_or_create(
            user_id=user_id,
            course_id=course_id,
            playlist_id=playlist_id,
        )
        submitted_at = now()
        exercise_data = dict(
            **data,
            id=exercise_id,  # rename
            # exercise_ID = exercise_id
            performed_at=dateformat.format(submitted_at, "Y-m-d H:i:s"),  # rename and reformat
            # server_date = datetime.isoformat(datetime.now())[:-3]+'Z' # UTC
        )

        pd.data.append(exercise_data)
        pd.full_clean()
        pd.save()

        if course_id:
            # Defensive ordering keeps .first() deterministic if duplicate rows exist.
            recurring_assignment = PlaylistCourseOrdered.objects.filter(
                course_id=course_id,
                playlist_id=playlist_id,
                is_recurring=True,
            ).order_by("order", "pk").first()
            if recurring_assignment is not None:
                rebuild_period_progress(
                    assignment=recurring_assignment,
                    performance_data=pd,
                    # Reuse the same captured submit timestamp to avoid boundary drift.
                    occurred_at=submitted_at,
                )

        try:
            if course_id:
                course = Course.objects.get(_id=course_id)
                print("\n")
                print(course, "len(pd.data):", len(pd.data))
                course.add_performance_to_dict(pd)
        except:
            pass
            # ERROR MESSAGE SHOULD READ: 'Failed to save course performance dictionary but proceeding to return performance data.''

        # the slicing of exercise_id ensures exercises are locked when performed in transposition
        exercise = Exercise.objects.get(id=exercise_id[0:6])
        if exercise.authored_by_id != user_id and not exercise.locked:
            exercise.lock()
        return pd

    def get_exercise_first_pass(self, exercise_id):
        for exercise in self.data:
            if exercise["id"] == exercise_id and exercise["error_tally"] in [
                0,
                -1,
                "n/a",
            ]:
                return exercise["performed_at"]
            elif exercise["id"] == exercise_id:
                continue
        return False

    def playlist_passed(self):
        from apps.dashboard.views.performance import playlist_pass_bool

        return playlist_pass_bool(
            self.playlist.exercise_list, self.data, len(self.playlist.exercise_list)
        )

    @cached_property
    def playlist_pass_date(self):
        from apps.dashboard.views.performance import playlist_pass_date

        return playlist_pass_date(
            self.playlist.exercise_list, self.data, len(self.playlist.exercise_list)
        )

    def exercise_is_performed(self, exercise_id):
        return any([exercise["id"] == exercise_id for exercise in self.data])

    def exercise_error_count(self, exercise_id):
        error_count = 0
        for exercise in self.data:
            if exercise["id"] == exercise_id and exercise["error_tally"] == 0:
                error_count = 0
            if exercise["id"] == exercise_id and exercise["error_tally"] not in [
                0,
                "n/a",
            ]:
                error_count = exercise["error_tally"]
        return error_count

    # @cached_property # this being a cached property caused the function call to fail
    def get_local_pass_date(self):
        from apps.dashboard.views.performance import playlist_pass_date

        pass_date_str = playlist_pass_date(
            exercise_list=self.playlist.exercise_list,
            exercises_data=self.data,
            playlist_length=len(self.playlist.exercise_list),
            make_concise_and_localize=False,
        )
        # UTC is assumed here since the performed_at property is written to the performance database per UTC
        pass_date_utc = datetime.strptime(pass_date_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=dt_timezone.utc
        )
        # for the user, interpret the pass_date in terms of the timezone for the course
        return pass_date_utc.astimezone(ZoneInfo(settings.TIME_ZONE))


@receiver(post_save, sender=Exercise)
@receiver(post_save, sender=Playlist)
@receiver(post_save, sender=Course)
@receiver(post_save, sender=PerformanceData)
def truncate_timestamps(sender, instance, *args, **kwargs):
    """Remove microseconds from 'created' and 'updated' fields"""
    connection = connections["default"]
    table_name = connection.ops.quote_name(instance._meta.db_table)
    pk_name = connection.ops.quote_name(instance._meta.pk.name)
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {table_name} "
            "SET created = DATE_TRUNC('second', created), updated = DATE_TRUNC('second', updated) "
            f"WHERE {pk_name} = %s",
            [instance.pk],
        )


    def __str__(self):
        return f"User:{self.user} Exercise:{self.exercise_id} at {self.submitted_at}"
