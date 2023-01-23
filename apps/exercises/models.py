import datetime
import re
from collections import OrderedDict
from datetime import timedelta, date
from itertools import product
from tabnanny import verbose

import pytz
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.core.validators import RegexValidator
from django.db import models, connections
from django.db.models import When, Case, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch
from django.utils import dateformat
from django.utils.dateparse import parse_datetime
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.safestring import mark_safe
from django_better_admin_arrayfield.models.fields import ArrayField

from apps.accounts.models import Group
from apps.exercises.constants import SIGNATURE_CHOICES, KEY_SIGNATURES
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
    id = models.CharField("ID", unique=True, max_length=16, null=True)
    description = models.CharField(
        "Description",
        max_length=60,
        blank=True,
        null=True,
        help_text="Brief description for your reference only; not seen by others.",
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
        ("roman_numerals", "Roman Numerals"),
        ("intervals", "Intervals"),
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
            updated__gt=now() - timedelta(hours=6),
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
    id = models.CharField("ID", unique=True, max_length=16, null=True)
    is_auto = models.BooleanField("Auto-generated", default=False)

    name = models.CharField(
        "Name",
        max_length=32,
    )
    authored_by = models.ForeignKey(
        "accounts.User",
        related_name="playlists",
        on_delete=models.PROTECT,
        verbose_name="Author of Unit",
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
        help_text="These are the exercises within this playlist. You can add exercises after creating the playlist. Changing the order will automatically save all changes made in the form.",
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

    TRANSPOSE_EXERCISE_LOOP = "Exercise Loop"
    TRANSPOSE_PLAYLIST_LOOP = "Playlist Loop"
    TRANSPOSE_EXERCISE_SHUFFLE = "Exercise Shuffle"
    TRANSPOSE_PLAYLIST_SHUFFLE = "Playlist Shuffle"
    TRANSPOSE_OFF = None
    TRANSPOSE_TYPE_CHOICES = (
        (TRANSPOSE_OFF, TRANSPOSE_OFF),
        (TRANSPOSE_EXERCISE_LOOP, TRANSPOSE_EXERCISE_LOOP),
        (TRANSPOSE_PLAYLIST_LOOP, TRANSPOSE_PLAYLIST_LOOP),
        # (TRANSPOSE_EXERCISE_SHUFFLE, TRANSPOSE_EXERCISE_SHUFFLE),
        # (TRANSPOSE_PLAYLIST_SHUFFLE, TRANSPOSE_PLAYLIST_SHUFFLE),
    )
    transposition_type = models.CharField(
        "Transposition Types",
        max_length=32,
        choices=TRANSPOSE_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="Determines order of transposed exercises. Exercise Loop means that each exercise will have its transposed versions come after it successively. Playlist Loop means that the entire playlist will come in its original key, followed successively by the playlist's transposed versions.",
    )
    is_public = models.BooleanField(
        "Commons",
        default=False,
        help_text="Sharing your playlist will allow other users to include it in their courses. Doing so will make your email visible to people looking to use this playlist.",
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
        sorted_exercise_list = list(map(lambda epo: epo.exercise, related_epos))
        return sorted_exercise_list

    @cached_property
    def exercise_list(self):
        if not self.is_transposed():
            return self.untransposed_exercises_ids

        return self.transposed_exercises_ids

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

        if self.transposition_type == self.TRANSPOSE_EXERCISE_LOOP:
            return list(product(sorted_exercise_list, self.transpose_requests))
        elif self.transposition_type == self.TRANSPOSE_PLAYLIST_LOOP:
            return [
                (t[1], t[0])
                for t in product(self.transpose_requests, sorted_exercise_list)
            ]

    @cached_property
    def transposed_exercises_ids(self):
        if not self.transposition_matrix:
            return []

        result = []
        for transposition in self.transposition_matrix:
            exercise_id, target_request = transposition
            exercise = Exercise.objects.get(id=exercise_id)
            result.append(transpose(exercise, target_request).id)
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
        if len(self.exercise_list) == 0:
            return
        try:
            exercise = Exercise.objects.filter(id=self.exercise_list[num - 1]).first()
        except (IndexError, TypeError):
            exercise = Exercise.objects.filter(id=self.exercise_list[-1]).first()

        if not self.is_transposed():
            return exercise

        # import pdb; pdb.set_trace()
        exercise_id, target_request = self.transposition_matrix[num - 1]
        exercise = Exercise.objects.get(id=exercise_id)
        transposed_exercise = transpose(exercise, target_request)
        # import pdb; pdb.set_trace()
        return transposed_exercise

    def get_exercise_url_by_num(
        self,
        num=1,
        course_id=None,
    ):
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
        return num

    def prev_num(self, num=1):
        if 1 < num <= self.exercise_count:
            return num - 1
        return 1

    def next(self, num=1):
        return self.get_exercise_obj_by_num(num + 1)

    def previous(self, num=1):
        return self.get_exercise_obj_by_num(num - 1)

    def __str__(self):
        return self.name

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

    # def clean_exercises(self):
    #     self.exercises = re.sub(" +", " ", self.exercises).strip()

    @cached_property
    def has_been_performed(self):
        return PerformanceData.objects.filter(playlist=self).exists()

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
        if self.order == None:
            self.order = len(
                ExercisePlaylistOrdered.objects.filter(
                    Q(exercise=self.exercise) & Q(playlist=self.playlist)
                )
            )
        super(ExercisePlaylistOrdered, self).save(*args, **kwargs)


class Course(ClonableModelMixin, BaseContentModel):
    id = models.CharField("ID", unique=True, max_length=16, blank=True)

    title = models.CharField(
        "Title",
        max_length=64,
    )

    open = models.BooleanField(
        "Open",
        default=True,
        help_text="Open courses can be viewed by your subscribers who have not performed any playlists within it.",
    )
    # slug = models.SlugField('URL slug', unique=True, max_length=64)
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
        help_text="These are the exercise playlists within the course. You can add playlists after creating the course. Changing the order will automatically save all changes made in the form.",
    )

    authored_by = models.ForeignKey(
        "accounts.User",
        related_name="courses",
        on_delete=models.PROTECT,
        verbose_name="Author",
    )
    is_public = models.BooleanField(
        "Commons",
        default=False,
        help_text="Sharing your course will make it available to other users. Doing so will make your email visible to people looking to use your course.",
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
        help_text="If no group is selected, course will be visible to all subscribers.",
        verbose_name="Visible Groups",
    )

    performance_dict = JSONField(default=dict, verbose_name="Performances", blank=True)

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    class Meta:
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        if not self._id:
            super(Course, self).save(*args, **kwargs)
        self.set_id(initial="C")
        super(Course, self).save(*args, **kwargs)

    @cached_property
    def has_been_performed(self):
        return False
        # return PerformanceData.objects.filter(playlist__name__in = re.split(r'[,; \n]+', self.playlists)).exists()

    @cached_property
    def playlist_id_list(self):
        return list(map(lambda p: p.id, self.playlists.all()))

    @cached_property
    def publish_dates_dict(self):
        pco_list = PlaylistCourseOrdered.objects.filter(course_id=self._id)
        return {
            Playlist.objects.get(_id=pco.playlist_id).id: pco.publish_date
            for pco in pco_list
        }

    @cached_property
    def due_dates_dict(self):
        pco_list = PlaylistCourseOrdered.objects.filter(
            course_id=self._id
        ).select_related("playlist")
        return {pco.playlist.id: pco.due_date for pco in pco_list}

    @cached_property
    def published_playlists(self):
        return self.playlists.all().filter(
            playlistcourseordered__publish_date__lt=date.today()
        )

    def get_due_date(self, playlist):
        tz_naive = PlaylistCourseOrdered.objects.get(
            Q(playlist_id=playlist._id, course_id=self._id)
        ).due_date
        return pytz.timezone(settings.TIME_ZONE).localize(tz_naive)


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

    # performance_dict = JSONField(default=dict, verbose_name="Performances", blank=True)

    # @cached_property
    # def performance_dict_test(self):
    #     print("fetching performances")
    #     data = {}
    #     course_playlists = list(
    #         PlaylistCourseOrdered.objects.filter(course=self)
    #         .order_by("order")
    #         .select_related("playlist")
    #     )
    #     playlist_num_dict = {pco.playlist: pco.order for pco in course_playlists}
    #     course_performances = PerformanceData.objects.filter(
    #         playlist__in=self.playlists.all()
    #     ).select_related("user", "playlist")

    #     due_dates = self.due_dates_dict

    #     for performance in course_performances:
    #         performer = performance.user
    #         playlist_num = playlist_num_dict[performance.playlist]

    #         pass_type = "P" if performance.playlist_passed else ""  # Pass

    #         if performance.playlist_passed:
    #             pass_date = performance.get_local_pass_date
    #             playlist_due_date = due_dates.get(performance.playlist.id)
    #             if playlist_due_date and playlist_due_date < pass_date:
    #                 diff = pass_date - playlist_due_date
    #                 days, seconds = diff.days, diff.seconds
    #                 hours = days * 24 + seconds // 3600

    #                 if hours >= 6:
    #                     pass_type = "T"

    #                 if days >= 7:
    #                     pass_type = "L"
    #         if performer not in data:
    #             data[performer] = {"time_elapsed": 0}
    #         data[performer].setdefault(playlist_num, mark_safe(pass_type))
    #         time_elapsed = 0
    #         for exercise_data in performance.data:
    #             time_elapsed += exercise_data["exercise_duration"]
    #         data[performer]["time_elapsed"] += int(time_elapsed)
    #     return data

    displayed_fields = ("due_date", "publish_date")


class PerformanceData(models.Model):
    user = models.ForeignKey(
        User, related_name="performance_data", on_delete=models.PROTECT
    )
    supervisor = models.ForeignKey(
        User,
        related_name="supervisor_performance_data",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
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
    playlist_performances = JSONField("Playlist Performances", default=list, blank=True)

    created = models.DateTimeField("Created", auto_now_add=True)
    updated = models.DateTimeField("Updated", auto_now=True)

    class Meta:
        verbose_name = "Performance"
        verbose_name_plural = "Performance Data"
        unique_together = (("user", "playlist", "course"),)

    def __str__(self):
        return f"Playlist:{self.playlist} - User:{self.user}"

    @classmethod
    def get_by_user(cls, user_id: int):
        return cls.objects.filter(user_id=user_id)

    @classmethod
    def get_by_playlist(cls, playlist_id: int):
        return cls.objects.filter(playlist_id=playlist_id)

    @classmethod
    def submit(
        cls,
        exercise_id: str,
        playlist_id: int,
        user_id: int,
        course_id: int,
        data: dict,
    ):
        pd, _ = cls.objects.get_or_create(
            course_id=course_id,
            playlist_id=playlist_id,
            user_id=user_id,
            supervisor_id=user_id,
        )
        exercise_data = dict(
            **data, id=exercise_id, performed_at=dateformat.format(now(), "Y-m-d H:i:s")
        )
        pd.data.append(exercise_data)
        pd.full_clean()
        pd.save()

        if course_id:
            pco = PlaylistCourseOrdered.objects.get(
                course_id=course_id, playlist_id=playlist_id
            )
            course = Course.objects.get(_id=course_id)
            performer = str(User.objects.get(id=user_id))
            pass_mark = "X"

            if pd.playlist_passed:
                pass_mark = "P"
                due_date = pco.due_date.replace(tzinfo=pytz.utc).astimezone(
                    pytz.timezone(settings.TIME_ZONE)
                )
                if due_date:
                    pass_date = pd.get_local_pass_date
                    if due_date < pass_date:
                        diff = pass_date - due_date
                        days, seconds = diff.days, diff.seconds
                        hours = days * 24 + seconds // 3600
                        if hours >= 6:
                            pass_mark = "T"
                        if days >= 7:
                            pass_mark = "L"
            if not (performer in course.performance_dict):
                course.performance_dict[performer] = {"time_elapsed": 0}
            course.performance_dict[performer][pco.order] = pass_mark
            for exercise_data in pd.data:
                course.performance_dict[performer]["time_elapsed"] += int(
                    exercise_data["exercise_duration"]
                )
            course.save()
        exercise = Exercise.objects.get(id=exercise_id[0:6])
        if exercise.authored_by_id != user_id and not exercise.locked:
            exercise.lock()

        return pd

    @classmethod
    def submit_playlist_performance(cls, playlist_id: int, user_id: int, data: dict):
        pd = cls.objects.filter(
            playlist_id=playlist_id, user_id=user_id, supervisor_id=user_id
        ).first()
        pd.playlist_performances.append(data)
        pd.full_clean()
        pd.save()

    def get_exercise_first_pass(self, exercise_id):
        for exercise in self.data:
            if exercise["id"] == exercise_id and exercise["exercise_error_tally"] in [
                0,
                -1,
                "n/a",
            ]:
                return exercise["performed_at"]
            elif exercise["id"] == exercise_id:
                continue
        return False

    @cached_property
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
            if exercise["id"] == exercise_id and exercise["exercise_error_tally"] == 0:
                error_count = 0
            if exercise["id"] == exercise_id and exercise[
                "exercise_error_tally"
            ] not in [0, "n/a"]:
                error_count = exercise["exercise_error_tally"]
        return error_count

    @cached_property
    def get_local_pass_date(self):
        from apps.dashboard.views.performance import playlist_pass_date

        pass_date = playlist_pass_date(
            exercise_list=self.playlist.exercise_list,
            exercises_data=self.data,
            playlist_length=len(self.playlist.exercise_list),
            reformat=False,
        )
        pass_date = datetime.datetime.strptime(pass_date, "%Y-%m-%d %H:%M:%S")
        return pytz.timezone(settings.TIME_ZONE).localize(pass_date)


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
