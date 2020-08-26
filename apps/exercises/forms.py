import string

from django import forms
from prettyjson import PrettyJSONWidget

from apps.exercises.models import Exercise, Playlist, PerformanceData


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        exclude = []
        widgets = {
            'data': PrettyJSONWidget(),
        }


class PlaylistForm(forms.ModelForm):
    class Meta:
        model = Playlist
        exclude = []
        widgets = {
            'exercises': forms.Textarea,
        }

    def clean(self):
        super(PlaylistForm, self).clean()
        exercise_ids = self.cleaned_data.get('exercises', '').split(',')
        exercise_ids = [id_.upper() for id_ in exercise_ids]
        available_exercises = list(Exercise.objects.values_list('id', flat=True))

        ranged_exercises = self._create_ranged_exercises(exercise_ids)

        exercise_ids += ranged_exercises
        exercise_ids = [f'{Exercise.zero_padding}{id_}' if len(id_) == 2 else id_ for id_ in exercise_ids]

        for id_ in exercise_ids:
            id_ = f'{Exercise.zero_padding}{id_}' if len(id_) == 2 else id_
            if id_ != '' and id_ not in available_exercises:
                self.add_error('exercises', f'Exercise with ID {id_} does not exist.')

        self.cleaned_data.update({'exercises': ','.join(exercise_ids)})

    def _create_ranged_exercises(self, exercise_ids):
        user_authored_exercises = list(Exercise.objects.filter(
            authored_by_id=self.context.get('user').id
        ).values_list('id', flat=True))

        ranged_exercises = []
        for id_ in exercise_ids:
            if '-' in id_:
                chars = string.ascii_uppercase
                lower, upper = id_.split('-')
                id_range = lower[:-1]
                char_range_lower, char_range_upper = chars.find(lower[-1]), chars.find(upper[-1])
                chars = chars[char_range_lower:char_range_upper + 1]
                for char in chars:
                    ranged_exercises.append(f'{id_range}{char}')
                exercise_ids.pop(exercise_ids.index(id_))
        ranged_exercises = [f'{Exercise.zero_padding}{id_}' if len(id_) == 2 else id_ for id_ in ranged_exercises]
        ranged_exercises = list(set(ranged_exercises).intersection(user_authored_exercises))
        return ranged_exercises


class PerformanceDataForm(forms.ModelForm):
    class Meta:
        model = PerformanceData
        exclude = []
        widgets = {
            'data': PrettyJSONWidget(),
            'playlist_performances': PrettyJSONWidget(),
        }
