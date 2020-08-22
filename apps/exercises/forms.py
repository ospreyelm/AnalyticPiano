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
        exercise_ids = self.cleaned_data['exercises'].split(',')
        available_exercises = list(Exercise.objects.values_list('id', flat=True))
        for id_ in exercise_ids:
            if id_ not in available_exercises:
                self.add_error('exercises', f'Exercise with ID {id_} does not exist.')


class PerformanceDataForm(forms.ModelForm):
    class Meta:
        model = PerformanceData
        exclude = []
        widgets = {
            'data': PrettyJSONWidget(),
            'playlist_performances': PrettyJSONWidget(),
        }
