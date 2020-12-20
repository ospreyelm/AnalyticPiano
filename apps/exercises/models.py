from collections import OrderedDict
from itertools import product

from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import When, Case
from django.urls import reverse, NoReverseMatch
from django.utils import dateformat
from django.utils.functional import cached_property
from django.utils.timezone import now
from django_better_admin_arrayfield.models.fields import ArrayField

from apps.exercises.constants import SIGNATURE_CHOICES, KEY_SIGNATURES
from apps.exercises.utils.transpose import transpose

User = get_user_model()


class RawJSONField(JSONField):
    """ To preserve the data order. """

    def db_type(self, connection):
        return 'json'


class Exercise(models.Model):
    _id = models.AutoField('_ID', unique=True, primary_key=True)
    id = models.CharField('ID', unique=True, max_length=16)

    data = RawJSONField('Data')
    rhythm_value = models.CharField('Rhythm', max_length=64,
                                    blank=True, null=True)
    is_public = models.BooleanField('Is Public', default=False)
    authored_by = models.ForeignKey('accounts.User',
                                    related_name='exercises',
                                    on_delete=models.PROTECT,
                                    verbose_name='Author')

    created = models.DateTimeField('Created', auto_now_add=True)
    updated = models.DateTimeField('Updated', auto_now=True)

    zero_padding = 'EA00A0'

    class Meta:
        verbose_name = 'Exercise'
        verbose_name_plural = 'Exercises'

    @classmethod
    def get_data_order_list(cls):
        return ['type', 'introText', 'reviewText', 'staffDistribution',
                'key', 'keySignature', 'analysis', 'highlight', 'chord']

    @property
    def is_private(self):
        return not self.is_public

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        if not self._id:
            super(Exercise, self).save(*args, **kwargs)
        self.set_id()
        self.sort_data()
        self.set_rhythm_values()
        super(Exercise, self).save(*args, **kwargs)

    def set_id(self):
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
        reverse_id += "E"
        self.id = reverse_id[::-1]

    def sort_data(self):
        if not all([key in self.data for key in self.get_data_order_list()]):
            return

        index_map = {v: i for i, v in enumerate(self.get_data_order_list())}
        self.data = OrderedDict(sorted(self.data.items(),
                                       key=lambda pair: index_map[pair[0]]))

    def set_rhythm_values(self):
        if not self.rhythm_value or not self.data:
            return

        supported_rhythm_values = ["w", "H", "h", "q", "1", "2", "4"]
        rhythm_values = self.rhythm_value.replace("1", "w").replace("2", "h").replace("4", "q")
        rhythm_values = [x for x in rhythm_values if x in supported_rhythm_values]
        chord_data = self.data.get('chord')
        del rhythm_values[len(chord_data):]  # truncate extra rhythms
        if len(rhythm_values) > 0 and len(rhythm_values) < len(chord_data):
            rhythm_values.append("w" * (len(chord_data) - len(rhythm_values)))
        self.rhythm_value = ' '.join(rhythm_values)

        for chord in chord_data:
            try:
                chord.update(rhythmValue=rhythm_values.pop(0))
            except IndexError:
                break
        self.data['chord'] = chord_data

    @cached_property
    def has_been_performed(self):
        return PerformanceData.objects.filter(data__contains=[{'id': self.id}]).exists()

    @property
    def lab_url(self):
        return reverse('lab:exercise-view', kwargs={'exercise_id': self.id})


class Playlist(models.Model):
    _id = models.AutoField('_ID', unique=True, primary_key=True)
    id = models.CharField('ID', unique=True, max_length=16)

    name = models.CharField('Name', unique=True, max_length=32)
    exercises = models.CharField('Exercises', max_length=1024,
                                 help_text='Ordered set of exercise IDs, separated by comma.')

    # TRANSPOSE
    transpose_requests = ArrayField(base_field=models.CharField(max_length=10, choices=SIGNATURE_CHOICES),
                                    default=list, blank=True, null=True,
                                    help_text=f'Valid choices are {" ".join(str(x) for x in KEY_SIGNATURES)}',
                                    verbose_name='Transpose Requests')

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
    authored_by = models.ForeignKey('accounts.User',
                                    related_name='playlists',
                                    on_delete=models.PROTECT,
                                    verbose_name='Authored By')

    created = models.DateTimeField('Created at', auto_now_add=True)
    updated = models.DateTimeField('Updated at', auto_now=True)

    class Meta:
        verbose_name = 'Playlist'
        verbose_name_plural = 'Playlists'

    @cached_property
    def exercise_list(self):
        if not self.is_transposed():
            return self.exercises.split(',')

        return self.transposed_exercises_ids

    @property
    def exercise_count(self):
        if not self.is_transposed():
            return len(self.exercise_list)

        return len(self.transposed_exercises_ids)

    @cached_property
    def transposition_matrix(self):
        if self.transposition_type == self.TRANSPOSE_EXERCISE_LOOP:
            return list(product(self.exercises.split(','), self.transpose_requests))
        elif self.transposition_type == self.TRANSPOSE_PLAYLIST_LOOP:
            return [(t[1], t[0]) for t in product(self.transpose_requests, self.exercises.split(','))]

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
                'lab:exercises',
                kwargs={"group_name": self.name,
                        "exercise_num": num}
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
        self.set_id()
        super(Playlist, self).save(*args, **kwargs)

    def set_id(self):
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
        reverse_id += "P"
        self.id = reverse_id[::-1]

    @cached_property
    def has_been_performed(self):
        return PerformanceData.objects.filter(playlist=self).exists()


def get_default_data():
    return {'exercises': []}


class PerformanceData(models.Model):
    user = models.ForeignKey(User, related_name='performance_data',
                             on_delete=models.PROTECT)
    supervisor = models.ForeignKey(User, related_name='supervisor_performance_data',
                                   blank=True, null=True,
                                   on_delete=models.PROTECT)
    playlist = models.ForeignKey(Playlist, related_name='performance_data',
                                 on_delete=models.PROTECT)
    data = JSONField('Raw Data', default=list)
    playlist_performances = JSONField('Playlist Performances', default=list, blank=True)

    created = models.DateTimeField('Created at', auto_now_add=True)
    updated = models.DateTimeField('Updated at', auto_now=True)

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
            if exercise['id'] == exercise_id and exercise['exercise_error_tally'] in [0, 'n/a']:
                return exercise['performed_at'].split()[0]
            elif exercise['id'] == exercise_id:
                continue
        return 'Not Passed'


class Course(models.Model):
    _id = models.AutoField('_ID', unique=True, primary_key=True)
    id = models.CharField('ID', unique=True, max_length=16)

    title = models.CharField('Title', unique=True, max_length=64)
    slug = models.SlugField('Slug', unique=True, max_length=64)
    playlists = models.CharField('Playlists', max_length=1024,
                                 help_text='Ordered set of playlist names or IDs, separated by comma.')

    authored_by = models.ForeignKey('accounts.User',
                                    related_name='courses',
                                    on_delete=models.PROTECT,
                                    verbose_name='Authored By')

    created = models.DateTimeField('Created at', auto_now_add=True)
    updated = models.DateTimeField('Updated at', auto_now=True)

    class Meta:
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        if not self._id:
            super(Course, self).save(*args, **kwargs)
        self.set_id()
        super(Course, self).save(*args, **kwargs)

    def set_id(self):
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
        reverse_id += "C"
        self.id = reverse_id[::-1]

    @cached_property
    def has_been_performed(self):
        return PerformanceData.objects.filter(playlist__name__in=self.playlists.split(',')).exists()
