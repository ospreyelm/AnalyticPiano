import datetime
from collections import OrderedDict
from datetime import timedelta
from itertools import product

from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import When, Case, Q
from django.urls import reverse, NoReverseMatch
from django.utils import dateformat
from django.utils.functional import cached_property
from django.utils.timezone import now
from django_better_admin_arrayfield.models.fields import ArrayField

from apps.exercises.constants import SIGNATURE_CHOICES, KEY_SIGNATURES
from apps.exercises.utils.transpose import transpose

import re

User = get_user_model()


class RawJSONField(JSONField):
    """ To preserve the data order. """

    def db_type(self, connection):
        return 'json'


class BaseContentModel(models.Model):
    _id = models.AutoField('_ID', unique=True, primary_key=True)

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


class ClonableModelMixin():
    @classmethod
    def get_unique_fields(cls):
        fields = []
        for field in cls._meta.fields:
            if field.unique:
                fields.append(field.name)
        return fields


class Exercise(ClonableModelMixin, BaseContentModel):
    id = models.CharField('ID', unique=True, max_length=16)
    description = models.CharField('Description', max_length=60,
                                   blank=True, null=True)
    data = RawJSONField('Data')
    rhythm = models.CharField('Rhythm', max_length=255,
                              blank=True, null=True)
    time_signature = models.CharField('Meter', max_length=8,
                                      blank=True, null=True, default='')
    is_public = models.BooleanField('Share', default=True)
    authored_by = models.ForeignKey('accounts.User',
                                    related_name='exercises',
                                    on_delete=models.PROTECT,
                                    verbose_name='Author')

    locked = models.BooleanField('Locked', default=False)

    created = models.DateTimeField('Created', auto_now_add=True)
    updated = models.DateTimeField('Updated', auto_now=True)

    zero_padding = 'EA00A0'

    ANALYSIS_MODE_CHOICES = (
        # not good that this is hard coded, where is this used currently?
        ("note_names", "Note Names"),
        ("scientific_pitch", "Scientific Pitch"),
        ("scale_degrees", "Scale Degrees"),
        ("solfege", "Solfege"),
        ("roman_numerals", "Roman Numerals"),
        ("intervals", "Intervals")
    )

    HIGHLIGHT_MODE_CHOICES = (
        ("roothighlight", "Root Highlight"),
        ("tritonehighlight", "Tritone Highlight")
    )

    class Meta:
        verbose_name = 'Exercise'
        verbose_name_plural = 'Exercises'

    @classmethod
    def get_data_order_list(cls):
        return ['type', 'introText', 'reviewText', 'staffDistribution',
                'key', 'keySignature', 'analysis', 'highlight', 'chord',
                'timeSignature']

    @property
    def is_private(self):
        return not self.is_public

    def __str__(self):
        return self.id

    def get_previous_authored_exercise(self):
        return Exercise.objects.filter(authored_by=self.authored_by, created__lt=self.created).last()

    def get_next_authored_exercise(self):
        return Exercise.objects.filter(authored_by=self.authored_by, created__gt=self.created).first()

    def validate_unique(self, exclude=None):
        if not self._id:
            return

        ## description need not be unique
        if Exercise.objects.exclude(id=self.id).filter(
                description=self.description,
                authored_by=self.authored_by
        ).exclude(Q(description='') | Q(description=None)).exists():
            raise ValidationError("Exercise with this name and this user already exists.")
        super(Exercise, self).validate_unique(exclude)

    def save(self, *args, **kwargs):
        if not self._id:
            super(Exercise, self).save(*args, **kwargs)
            self.set_id(initial='E')
            self.set_auto_playlist()

        # self.validate_unique()
        self.set_id(initial='E')
        self.sort_data()
        self.set_rhythm_values()
        super(Exercise, self).save(*args, **kwargs)

    def sort_data(self):
        if not all([key in self.data for key in self.get_data_order_list()]):
            return

        index_map = {v: i for i, v in enumerate(self.get_data_order_list())}
        self.data = OrderedDict(sorted(self.data.items(),
                                       key=lambda pair: index_map[pair[0]]))

    def set_rhythm_values(self):
        if not self.rhythm or not self.data:
            return

        supported_rhythm_values = ["w", "H", "h", "q", "1", "2", "4"]
        rhythm_values = self.rhythm.replace("1", "w").replace("2", "h").replace("4", "q")
        rhythm_values = [x for x in rhythm_values if x in supported_rhythm_values]
        chord_data = self.data.get('chord')
        del rhythm_values[len(chord_data):]  # truncate extra rhythms
        if len(rhythm_values) > 0 and len(rhythm_values) < len(chord_data):
            rhythm_values.append("w" * (len(chord_data) - len(rhythm_values)))
        self.rhythm = ' '.join(rhythm_values)

        for chord in chord_data:
            try:
                chord.update(rhythmValue=rhythm_values.pop(0))
            except IndexError:
                break
        self.data['chord'] = chord_data

    def set_auto_playlist(self):
        auto_playlist = Playlist.objects.filter(
            authored_by=self.authored_by,
            is_auto=True,
            updated__gt=now() - timedelta(hours=6)
        ).last()
        if auto_playlist is None:
            auto_playlist = Playlist.create_auto_playlist(authored_by=self.authored_by,
                                                          initial_exercise_id=self.id)
        lately_edited_playlists = Playlist.objects.filter(updated__gt=auto_playlist.updated)
        if lately_edited_playlists.exists():
            Playlist.create_auto_playlist(authored_by=self.authored_by,
                                          initial_exercise_id=self.id)
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
        return reverse('lab:exercise-view', kwargs={'exercise_id': self.id})

    def set_data_modes(self, field_name, modes, enabled):
        if field_name not in self.data:
            return

        _data = self.data.get(field_name)
        for mode in _data['mode']:
            if modes and mode in modes:
                _data['mode'][mode] = True
            elif not modes or mode not in modes:
                _data['mode'][mode] = False

        self.data[field_name] = _data
        self.data[field_name]['enabled'] = enabled
        return self

    def lock(self):
        self.locked = True
        self.save()


class Playlist(ClonableModelMixin, BaseContentModel):
    id = models.CharField('ID', unique=True, max_length=16)

    name = models.CharField(
        'Name', unique=True, max_length=32,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9-_]+$',
                message='Use letters, numbers, underscores, or hyphens',
            )]
    )
    is_public = models.BooleanField('Share', default=False)
    is_auto = models.BooleanField('Is Auto Playlist', default=False)
    authored_by = models.ForeignKey('accounts.User',
                                    related_name='playlists',
                                    on_delete=models.PROTECT,
                                    verbose_name='Author of Unit')

    created = models.DateTimeField('Created', auto_now_add=True)
    updated = models.DateTimeField('Updated', auto_now=True)

    exercises = models.CharField(
        'Exercise IDs',
        max_length=1024,
        # help_text='Ordered set of exercise IDs, separated by comma, semicolon, space, or newline.'
    )

    transpose_requests = ArrayField(base_field=models.CharField(max_length=10, choices=SIGNATURE_CHOICES),
                                    default=list, blank=True, null=True,
                                    help_text=f'Valid choices are {" ".join(str(x) for x in KEY_SIGNATURES)}',
                                    verbose_name='Transpose requests')

    TRANSPOSE_EXERCISE_LOOP = 'Exercise Loop'
    TRANSPOSE_PLAYLIST_LOOP = 'Playlist Loop'
    TRANSPOSE_EXERCISE_SHUFFLE = 'Exercise Shuffle'
    TRANSPOSE_PLAYLIST_SHUFFLE = 'Playlist Shuffle'
    TRANSPOSE_OFF = None
    TRANSPOSE_TYPE_CHOICES = (
        (TRANSPOSE_EXERCISE_LOOP, TRANSPOSE_EXERCISE_LOOP),
        (TRANSPOSE_PLAYLIST_LOOP, TRANSPOSE_PLAYLIST_LOOP),
        # (TRANSPOSE_EXERCISE_SHUFFLE, TRANSPOSE_EXERCISE_SHUFFLE),
        # (TRANSPOSE_PLAYLIST_SHUFFLE, TRANSPOSE_PLAYLIST_SHUFFLE),
        (TRANSPOSE_OFF, TRANSPOSE_OFF)
    )
    transposition_type = models.CharField('Transposition Types', max_length=32,
                                          choices=TRANSPOSE_TYPE_CHOICES, blank=True, null=True)
    zero_padding = 'PA00A0'

    class Meta:
        verbose_name = 'Playlist'
        verbose_name_plural = 'Playlists'

    @cached_property
    def exercise_list(self):
        if not self.is_transposed():
            return re.split(r'[,; \n]+', self.exercises)

        return self.transposed_exercises_ids

    @property
    def exercise_count(self):
        if not self.is_transposed():
            return len(self.exercise_list)

        return len(self.transposed_exercises_ids)

    @cached_property
    def transposition_matrix(self):
        if self.transposition_type == self.TRANSPOSE_EXERCISE_LOOP:
            return list(product(
                re.split(r'[,; \n]+', self.exercises),
                self.transpose_requests
            ))
        elif self.transposition_type == self.TRANSPOSE_PLAYLIST_LOOP:
            return [(t[1], t[0]) for t in product(
                self.transpose_requests,
                re.split(r'[,; \n]+', self.exercises)
            )]

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

        exercises = Exercise.objects.filter(id__in=self.exercise_list).annotate(
            _sort_index=Case(*whens, output_field=models.CharField())
        ).order_by('_sort_index')

        return exercises

    def append_exercise(self, exercise_id):
        if self.exercises == '':
            self.exercises = exercise_id
        elif exercise_id not in self.exercises:
            self.exercises += f', {exercise_id}'
        self.save()

    def is_transposed(self):
        return self.transpose_requests and self.transposition_type

    def get_exercise_obj_by_num(self, num=1):
        try:
            exercise = Exercise.objects.filter(id=self.exercise_list[num - 1]).first()
        except (IndexError, TypeError):
            exercise = Exercise.objects.filter(id=self.exercise_list[-1]).first()

        if not self.is_transposed():
            return exercise

        # print(self.transposed_exercises[num])
        # import pdb; pdb.set_trace()
        exercise_id, target_request = self.transposition_matrix[num - 1]
        exercise = Exercise.objects.get(id=exercise_id)
        transposed_exercise = transpose(exercise, target_request)
        # import pdb; pdb.set_trace()
        return transposed_exercise

    def get_exercise_url_by_num(self, num=1):
        try:
            return reverse(
                'lab:playlist-view',
                kwargs={"playlist_name": self.name,
                        "exercise_num": num}
            )
        except NoReverseMatch:
            return None

    def get_exercise_url_by_id(self, id):
        try:
            exercise_num = self.exercise_list.index(id) + 1
        except ValueError:
            # print ('playlist changed since this exercise performed', id, self.exercise_list);
            return None
        try:
            return reverse(
                'lab:playlist-view',
                kwargs={"playlist_name": self.name,
                        "exercise_num": exercise_num}
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

    def save(self, *args, **kwargs):
        if not self._id:
            super(Playlist, self).save(*args, **kwargs)
        self.set_id(initial='P')
        self.set_auto_name()
        super(Playlist, self).save(*args, **kwargs)

    @cached_property
    def has_been_performed(self):
        return PerformanceData.objects.filter(playlist=self).exclude(user=self.authored_by).exists()

    @classmethod
    def create_auto_playlist(cls, initial_exercise_id, authored_by):
        auto_playlist = Playlist(authored_by=authored_by,
                                 exercises=initial_exercise_id,
                                 is_auto=True)
        auto_playlist.save()
        return auto_playlist

    def set_auto_name(self):
        if self.is_auto and not self.name:
            auto_id = list(self.id)
            auto_id[0] = 'U'
            auto_id = ''.join(auto_id)
            date, time = now().date().strftime('%Y%m%d'), now().time().strftime('%H%M')
            self.name = f'{auto_id}_{date}_{time}'


def get_default_data():
    return {'exercises': []}


class Course(ClonableModelMixin, BaseContentModel):
    id = models.CharField('ID', unique=True, max_length=16)

    title = models.CharField(
        'Title', unique=True, max_length=64,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9-_]+$',
                message='Use letters, numbers, underscores, or hyphens',
            )]
    )
    slug = models.SlugField('URL slug', unique=True, max_length=64)
    playlists = models.CharField(
        'Playlist IDs',
        max_length=1024,
        # PLEASEFIX make this required=False,
        # help_text='Ordered set of playlist IDs, separated by comma, semicolon, space, or newline.'
    )

    authored_by = models.ForeignKey('accounts.User',
                                    related_name='courses',
                                    on_delete=models.PROTECT,
                                    verbose_name='Author')
    is_public = models.BooleanField('Share', default=False)

    publish_dates = models.CharField('Publish Dates', max_length=1024, blank=True, null=True,
                                     help_text='Publish date of each playlist, separated by space.')

    due_dates = models.CharField('Due Dates', max_length=1024, blank=True, null=True,
                                 help_text='Due date of each playlist, separated by space.')

    created = models.DateTimeField('Created', auto_now_add=True)
    updated = models.DateTimeField('Updated', auto_now=True)

    class Meta:
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        if not self._id:
            super(Course, self).save(*args, **kwargs)
        self.set_id(initial='C')
        super(Course, self).save(*args, **kwargs)

    @cached_property
    def has_been_performed(self):
        return False
        # return PerformanceData.objects.filter(playlist__name__in = re.split(r'[,; \n]+', self.playlists)).exists()

    @property
    def split_playlist_ids(self):
        return re.split(r'[,; \n]+', self.playlists)

    @cached_property
    def playlist_objects(self):
        return Playlist.objects.filter(id__in=self.split_playlist_ids)

    @property
    def publish_dates_dict(self):
        return dict(zip(self.playlists.split(' '), self.publish_dates.split(' ')))

    @property
    def due_dates_dict(self):
        return dict(zip(self.playlists.split(' '), self.due_dates.split(' ')))

    @cached_property
    def published_playlists(self):
        if not self.publish_dates:
            return self.playlist_objects

        published_playlists = [playlist_id for playlist_id, publish_date in self.publish_dates_dict.items()
                               if now().date() >= datetime.datetime.strptime(publish_date, '%Y-%m-%d').date()]
        return self.playlist_objects.filter(id__in=published_playlists)


class PerformanceData(models.Model):
    user = models.ForeignKey(User, related_name='performance_data',
                             on_delete=models.PROTECT)
    supervisor = models.ForeignKey(User, related_name='supervisor_performance_data',
                                   blank=True, null=True,
                                   on_delete=models.PROTECT)
    playlist = models.ForeignKey(Playlist, related_name='performance_data',
                                 on_delete=models.PROTECT)
    # course = models.ForeignKey(Course, related_name='performance_data',
    #                            on_delete=models.PROTECT, blank=True, null=True)
    data = JSONField('Raw Data', default=list)
    playlist_performances = JSONField('Playlist Performances', default=list, blank=True)

    created = models.DateTimeField('Created', auto_now_add=True)
    updated = models.DateTimeField('Updated', auto_now=True)

    class Meta:
        verbose_name = 'Performance'
        verbose_name_plural = 'Performance Data'
        unique_together = (('user', 'playlist'),)

    def __str__(self):
        return f'Playlist:{self.playlist} - User:{self.user}'

    @classmethod
    def get_by_user(cls, user_id: int):
        return cls.objects.filter(user_id=user_id)

    @classmethod
    def get_by_playlist(cls, playlist_id: int):
        return cls.objects.filter(playlist_id=playlist_id)

    @classmethod
    def submit(cls, exercise_id: str, playlist_id: int,
               user_id: int, data: dict):
        pd, _ = cls.objects.get_or_create(playlist_id=playlist_id,
                                          user_id=user_id,
                                          supervisor_id=user_id)
        exercise_data = dict(
            **data,
            id=exercise_id,
            performed_at=dateformat.format(now(), 'Y-m-d H:i:s')
        )
        pd.data.append(exercise_data)
        pd.full_clean()
        pd.save()

        exercise = Exercise.objects.get(id=exercise_id)
        if exercise.authored_by_id != user_id and not exercise.locked:
            exercise.lock()

        return pd

    @classmethod
    def submit_playlist_performance(cls, playlist_id: int,
                                    user_id: int, data: dict):
        pd = cls.objects.filter(playlist_id=playlist_id,
                                user_id=user_id,
                                supervisor_id=user_id).first()
        pd.playlist_performances.append(data)
        pd.full_clean()
        pd.save()
        return pd

    def get_exercise_first_pass(self, exercise_id):
        for exercise in self.data:
            if exercise['id'] == exercise_id and exercise['exercise_error_tally'] in [0, -1, 'n/a']:
                return exercise['performed_at']
            elif exercise['id'] == exercise_id:
                continue
        return False

    @property
    def playlist_passed(self):
        from apps.dashboard.views.performance import playlist_pass_bool
        return playlist_pass_bool(self.playlist.exercise_list, self.data, len(self.playlist.exercise_list))

    @property
    def playlist_pass_date(self):
        from apps.dashboard.views.performance import playlist_pass_date
        return playlist_pass_date(self.playlist.exercise_list, self.data, len(self.playlist.exercise_list))

    def exercise_is_performed(self, exercise_id):
        return any([exercise['id'] == exercise_id for exercise in self.data])

    def exercise_error_count(self, exercise_id):
        error_count = 0
        for exercise in self.data:
            if exercise['id'] == exercise_id and exercise['exercise_error_tally'] == 0:
                error_count = 0
            if exercise['id'] == exercise_id and exercise['exercise_error_tally'] not in [0, 'n/a']:
                error_count = exercise['exercise_error_tally']
        return error_count
