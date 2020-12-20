from django import forms
from django.contrib.auth import get_user_model
from prettyjson import PrettyJSONWidget

from apps.accounts.models import KEYBOARD_CHOICES
from apps.exercises.forms import ExerciseForm, PlaylistForm, CourseForm
from apps.exercises.models import Exercise

User = get_user_model()


class AddSupervisorForm(forms.Form):
    email = forms.EmailField(label='Enter supervisor email:')


class AddSubscriberForm(forms.Form):
    email = forms.EmailField(label='Enter subscriber email:')


class KeyboardForm(forms.Form):
    keyboard_size = forms.ChoiceField(widget=forms.Select(), choices=KEYBOARD_CHOICES, initial=49)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(KeyboardForm, self).__init__(*args, **kwargs)


class DashboardExerciseForm(ExerciseForm):
    class Meta:
        model = Exercise
        exclude = ['data', 'authored_by']
        widgets = {
            'data': PrettyJSONWidget(attrs={'initial': 'parsed'}),
            'id': forms.TextInput(attrs={'readonly': 'readonly'}),
        }


class TransposeRequestsField(forms.CharField):
    def to_python(self, value):
        value = super(TransposeRequestsField, self).to_python(value)
        return value.replace(' ', '').split(',')

    def prepare_value(self, value):
        if value is None:
            return

        value = super(TransposeRequestsField, self).prepare_value(value)
        if isinstance(value, str):
            return value
        return ','.join(value)


class DashboardAddPlaylistForm(PlaylistForm):
    transpose_requests = TransposeRequestsField(label='Transpose Request')

    class Meta(PlaylistForm.Meta):
        exclude = ['id', 'authored_by']


class DashboardCourseForm(CourseForm):
    class Meta(CourseForm.Meta):
        exclude = ['id', 'authored_by']
