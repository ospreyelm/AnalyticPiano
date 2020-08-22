from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.urls import reverse, NoReverseMatch
from django.utils import dateformat
from django.utils.functional import cached_property
from django.utils.timezone import now

User = get_user_model()


class Exercise(models.Model):
    _id = models.AutoField('_ID', unique=True, primary_key=True)
    id = models.CharField('ID', unique=True, max_length=16)

    data = JSONField('Data')
    is_public = models.BooleanField('Is Public', default=False)
    authored_by = models.ForeignKey('accounts.User',
                                    related_name='exercises',
                                    on_delete=models.PROTECT,
                                    verbose_name='Authored By')

    created = models.DateTimeField('Created at', auto_now_add=True)
    updated = models.DateTimeField('Updated at', auto_now=True)

    class Meta:
        verbose_name = 'Exercise'
        verbose_name_plural = 'Exercises'

    @property
    def is_private(self):
        return not self.is_public

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        if not self._id:
            super(Exercise, self).save(*args, **kwargs)
        self.set_id()
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


class Playlist(models.Model):
    _id = models.AutoField('_ID', unique=True, primary_key=True)
    id = models.CharField('ID', unique=True, max_length=16)

    name = models.CharField('Name', unique=True, max_length=32)
    exercises = models.CharField('Exercises', max_length=1024,
                                 help_text='Ordered set of exercise IDs, separated by comma.')
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
        return self.exercises.split(',')

    @property
    def exercise_count(self):
        return len(self.exercise_list)

    @property
    def exercise_objects(self):
        return Exercise.objects.filter(id__in=self.exercise_list)

    def get_exercise_obj_by_num(self, num=1):
        try:
            return Exercise.objects.filter(id=self.exercise_list[num - 1]).first()
        except IndexError:
            return Exercise.objects.filter(id=self.exercise_list[-1]).first()

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
        if len(self.exercise_list) > 0:
            return self.exercise_list[0]
        return None

    def last(self):
        if len(self.exercise_list) > 0:
            return self.exercise_list[-1]
        return None

    def next_num(self, num=1):
        if num < self.exercise_count:
            return num + 1
        return None

    def prev_num(self, num=1):
        if 1 < num < self.exercise_count:
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
        verbose_name_plural = 'Performances'
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
