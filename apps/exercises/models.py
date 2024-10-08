import re
from collections import OrderedDict
from datetime import timedelta, date, datetime
from itertools import product
from tabnanny import verbose

import pytz
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
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

from apps.accounts.models import Group
from apps.exercises.constants import (
    SIGNATURE_CHOICES,
    KEY_SIGNATURES,
    pseudo_key_to_sig,
)
from apps.exercises.utils.transpose import transpose

import re

User = get_user_model()


class RawJSONField(JSONField):
    """To preserve the data order."""

    def db_type(self, connection):
        return "json"


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

    locked = models.BooleanField("Locked", default=False)

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

    def get_previous_authored_exercise(self):
        return Exercise.objects.filter(
            authored_by=self.authored_by, created__lt=self.created
        ).last()

    def get_next_authored_exercise(self):
        return Exercise.objects.filter(
            authored_by=self.authored_by, created__gt=self.created
        ).first()

    def save(self, *args, **kwargs):
        if not self._id:
            super(Exercise, self).save(*args, **kwargs)
            self.set_id(initial="E")
            self.save()
            self.set_auto_playlist()

        # self.validate_unique()
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


@receiver(models.signals.post_delete, sender=Exercise)
def remove_exercise_from_playlists(sender, instance, *args, **kwargs):
    """
    Remove the deleted exercise from all playlists that contain it
    """
    Playlist.remove_exercise_from_playlists(exercise_id=instance._id)


class Playlist(ClonableModelMixin, BaseContentModel):
    id = models.CharField("P-ID", unique=True, max_length=16, null=True)
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

    zero_padding = "PA00A0"

    class Meta:
        verbose_name = "Playlist"
        verbose_name_plural = "Playlists"

    @cached_property
    def untransposed_exercises_ids(self):
        related_epos = ExercisePlaylistOrdered.objects.filter(playlist=self).order_by(
            "order"
        )
        sorted_exercise_list = list(map(lambda epo: epo.exercise.id, related_epos))
        return sorted_exercise_list

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

    @property
    def exercise_count(self):
        if not self.is_transposed():
            return len(self.exercises.all())

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
                tzinfo=pytz.timezone(settings.TIME_ZONE)
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
                tzinfo=pytz.timezone(settings.TIME_ZONE)
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
        return due_date_of_playlist.replace(tzinfo=pytz.timezone(settings.TIME_ZONE))
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
                    tzinfo=pytz.timezone(settings.TIME_ZONE)
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

    displayed_fields = ("due_date", "publish_date")


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
        exercise_data = dict(
            **data,
            id=exercise_id,  # rename
            # exercise_ID = exercise_id
            performed_at=dateformat.format(now(), "Y-m-d H:i:s"),  # rename and reformat
            # server_date = datetime.isoformat(datetime.now())[:-3]+'Z' # UTC
        )

        pd.data.append(exercise_data)
        pd.full_clean()
        pd.save()
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
            tzinfo=pytz.timezone("UTC")
        )
        # for the user, interpret the pass_date in terms of the timezone for the course
        return pass_date_utc.astimezone(pytz.timezone(settings.TIME_ZONE))


@receiver(post_save, sender=Exercise)
@receiver(post_save, sender=Playlist)
@receiver(post_save, sender=Course)
@receiver(post_save, sender=PerformanceData)
def truncate_timestamps(sender, instance, *args, **kwargs):
    """Remove microseconds from 'created' and 'updated' fields"""
    with connections["default"].cursor() as cursor:
        cursor.execute(
            "UPDATE {} "
            "SET created = DATE_TRUNC('second', created), updated = DATE_TRUNC('second', updated) "
            "WHERE {} = {}".format(
                instance._meta.db_table, instance._meta.pk.name, instance.pk
            )
        )
