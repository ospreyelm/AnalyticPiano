import string, re

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

    DISTRIBUTION_KEYBOARD = 'keyboard'
    DISTRIBUTION_CHORALE = 'chorale'
    DISTRIBUTION_LH = 'LH'
    DISTRIBUTION_RH = 'RH'
    DISTRIBUTION_KEYBOARD_RH_PREFERENCE = 'keyboardPlusRHBias'
    DISTRIBUTION_KEYBOARD_LH_PREFERENCE = 'keyboardPlusLHBias'

    DISTRIBUTION_CHOICES = (
        (DISTRIBUTION_KEYBOARD, DISTRIBUTION_KEYBOARD),
        (DISTRIBUTION_CHORALE, DISTRIBUTION_CHORALE),
        (DISTRIBUTION_LH, DISTRIBUTION_LH),
        (DISTRIBUTION_RH, DISTRIBUTION_RH),
        (DISTRIBUTION_KEYBOARD_RH_PREFERENCE, DISTRIBUTION_KEYBOARD_RH_PREFERENCE),
        (DISTRIBUTION_KEYBOARD_LH_PREFERENCE, DISTRIBUTION_KEYBOARD_LH_PREFERENCE)
    )

    intro_text = forms.CharField(widget=CKEditorWidget(config_name="safe"), required=False)
    review_text = forms.CharField(widget=CKEditorWidget(config_name="safe"), required=False)
    type = forms.ChoiceField(choices=TYPE_CHOICES, widget=forms.RadioSelect(), required=False)
    staff_distribution = forms.ChoiceField(choices=DISTRIBUTION_CHOICES, widget=forms.RadioSelect(), required=False)

    def __init__(self, *arg, **kwargs):
        super(ExerciseForm, self).__init__(*arg, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['intro_text'].initial = self.instance.data.get('introText', None)
            self.fields['review_text'].initial = self.instance.data.get('reviewText', None)
            self.fields['type'].initial = self.instance.data.get('type', self.TYPE_MATCHING)
            self.fields['staff_distribution'].initial = self.instance.data.get('staffDistribution', self.DISTRIBUTION_KEYBOARD)

    def save(self, commit=True):
        instance = super(ExerciseForm, self).save(commit)

        if instance:
            instance.data['introText'] = self.cleaned_data['intro_text']
            instance.data['reviewText'] = self.cleaned_data['review_text']
            instance.data['type'] = self.cleaned_data['type']
            instance.data['staffDistribution'] = self.cleaned_data['staff_distribution']
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
    transposition_type = forms.ChoiceField(choices=Playlist.TRANSPOSE_TYPE_CHOICES,
                                           widget=forms.RadioSelect(), required=False)

    class Meta:
        model = Playlist
        exclude = []
        widgets = {
            'exercises': forms.Textarea,
        }

    def clean(self):
        super(PlaylistForm, self).clean()

        parsed_input = [n.upper().strip() for n in
            re.split('-*[,; ]+-*',
                self.cleaned_data.get('exercises', '')
            )
        ]
        id_ranges = list(filter(lambda x: '-' in x, parsed_input))
        single_ids = list(filter(lambda x: '-' not in x, parsed_input))

        exercise_ids = []
        for item in single_ids:
            if len(item) <= 6:
                full_id = f'{Exercise.zero_padding[:-len(item)]}{item}'
                exercise_ids.append(full_id)

        for id_range in id_ranges:
            for item in self._expand_exercise_range(id_range):
                exercise_ids.append(item)

        all_exercises = list(Exercise.objects.values_list('id', flat=True))
        for item in exercise_ids:
            if item not in all_exercises:
                # also remove from list?
                self.add_error('exercises',
                    f'Exercise with ID {id_} does not exist.')

        self.cleaned_data.update({'exercises': ','.join(exercise_ids)})

    def _integer_from_id(self, ex_str):
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        digits = "0123456789"
        bases = [26, 26, 10, 10, 26]
        reverse_str = ex_str[::-1]
        integer = 0
        base = 1
        for i in range(len(reverse_str)):
            char = reverse_str[i]
            if char in letters:
                integer += base * letters.index(char)
                base *= 26
            elif char in digits:
                integer += base * digits.index(char)
                base *= 10
            else:
                return None
        return integer

    def _id_from_integer(self, num):
        # must accord with models.py (do not make format changes)
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        reverse_id = ""
        bases = [26, 26, 10, 10, 26]
        for base in bases:
            if base == 26:
                reverse_id += letters[num % base]
            elif base == 10:
                reverse_id += str(num % base)
            num //= base
        if num != 0 or len(reverse_id) != len(bases):
            return None
        reverse_id += "E"
        return reverse_id[::-1]

    def _expand_exercise_range(self, id_range):
        user_authored_exercises = list(Exercise.objects.filter(
            authored_by_id=self.context.get('user').id
        ).values_list('id', flat=True).order_by('id'))

        exercise_ids = []

        split_input = re.split('-+', id_range)
        if len(split_input) >= 2:
            lower = self._integer_from_id(split_input[0])
            upper = self._integer_from_id(split_input[-1])
            if not lower < upper:
                return exercise_ids
            for num in range(lower, upper + 1):
                item = self._id_from_integer(num)
                if item in user_authored_exercises:
                    # Self-authored exercises only
                    exercise_ids.append(item)

        return exercise_ids


class PerformanceDataForm(forms.ModelForm):
    class Meta:
        model = PerformanceData
        exclude = []
        widgets = {
            'data': PrettyJSONWidget(),
            'playlist_performances': PrettyJSONWidget(),
        }
