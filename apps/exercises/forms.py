import string

from ckeditor.widgets import CKEditorWidget
from django import forms
from prettyjson import PrettyJSONWidget

from apps.exercises.models import Exercise, Playlist, PerformanceData


class ExerciseForm(forms.ModelForm):
    TYPE_MATCHING = 'matching'
    TYPE_ANALYTICAL = 'analytical'
    TYPE_ANALYTICAL_PCS = 'analytical_pcs'
    TYPE_FIGURED_BASS = 'figured_bass'
    TYPE_FIGURED_BASS_PCS = 'figured_bass_pcs'
    TYPE_CHOICES = (
        (TYPE_MATCHING, TYPE_MATCHING),
        (TYPE_ANALYTICAL, TYPE_ANALYTICAL),
        (TYPE_ANALYTICAL_PCS, TYPE_ANALYTICAL_PCS),
        (TYPE_FIGURED_BASS, TYPE_FIGURED_BASS),
        (TYPE_FIGURED_BASS_PCS, TYPE_FIGURED_BASS_PCS)
    )

    intro_text = forms.CharField(widget=CKEditorWidget(config_name="safe"), required=False)
    review_text = forms.CharField(widget=CKEditorWidget(config_name="safe"), required=False)
    type = forms.ChoiceField(choices=TYPE_CHOICES, widget=forms.RadioSelect(), required=False)

    def __init__(self, *arg, **kwargs):
        super(ExerciseForm, self).__init__(*arg, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['intro_text'].initial = self.instance.data.get('introText', None)
            self.fields['review_text'].initial = self.instance.data.get('reviewText', None)
            self.fields['type'].initial = self.instance.data.get('type', self.TYPE_MATCHING)

    def save(self, commit=True):
        instance = super(ExerciseForm, self).save(commit)

        if instance:
            instance.data['introText'] = self.cleaned_data['intro_text']
            instance.data['reviewText'] = self.cleaned_data['review_text']
            instance.data['type'] = self.cleaned_data['type']
            instance.authored_by = self.context.get('user')
            instance.clean()
            instance.save()

        return instance

    class Meta:
        model = Exercise
        fields = '__all__'
        widgets = {
            'data': PrettyJSONWidget(attrs={'initial': 'parsed'}),
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
        exercise_ids = [id_.upper().strip() for id_ in exercise_ids]
        all_exercises = list(Exercise.objects.values_list('id', flat=True))

        ranged_exercises = self._create_ranged_exercises(exercise_ids)

        exercise_ids = list(filter(lambda x: '-' not in x, exercise_ids))
        exercise_ids += ranged_exercises
        exercise_ids = [f'{Exercise.zero_padding[:-1] if len(id_) == 2  else Exercise.zero_padding}{id_}'
                        if len(id_) <= 2 else id_ for id_ in exercise_ids]

        for id_ in exercise_ids:
            if id_ != '' and id_ not in all_exercises:
                self.add_error('exercises', f'Exercise with ID {id_} does not exist.')
        self.cleaned_data.update({'exercises': ','.join(exercise_ids)})

    def _create_ranged_exercises(self, exercise_ids):
        user_authored_exercises = list(Exercise.objects.filter(
            authored_by_id=self.context.get('user').id
        ).values_list('id', flat=True).order_by('id'))

        ranged_exercises = []
        ascii_chars = string.ascii_uppercase

        for id_ in exercise_ids:
            if '-' in id_ and len(id_.split('-')) == 2:
                lower, upper = id_.split('-')
                id_range = lower[:-1]
                char_range_lower, char_range_upper = ascii_chars.find(lower[-1]), ascii_chars.find(upper[-1])
                chars = sorted(ascii_chars[char_range_lower:char_range_upper + 1])
                for idx in range(len(chars)):
                    ranged_exercises.append(f'{id_range}{chars[idx]}')
        ranged_exercises = [f'{Exercise.zero_padding[:-1] if len(id_) == 2 else Exercise.zero_padding}{id_}'
                            if len(id_) <= 2 else id_ for id_ in ranged_exercises]
        ranged_exercises = sorted(set(ranged_exercises).intersection(user_authored_exercises),
                                  key=lambda x: ranged_exercises.index(x))
        ranged_exercises = list(ranged_exercises)
        return ranged_exercises


class PerformanceDataForm(forms.ModelForm):
    class Meta:
        model = PerformanceData
        exclude = []
        widgets = {
            'data': PrettyJSONWidget(),
            'playlist_performances': PrettyJSONWidget(),
        }
