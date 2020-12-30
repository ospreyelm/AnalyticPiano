from django import forms
from django.contrib.auth import get_user_model
from django.contrib.postgres.forms import JSONField
from prettyjson import PrettyJSONWidget

from apps.accounts.models import KEYBOARD_CHOICES
from apps.exercises.forms import ExerciseForm, PlaylistForm, CourseForm
from apps.exercises.models import Exercise

User = get_user_model()


class BaseSupervisionForm(forms.Form):
    def clean(self):
        email = self.cleaned_data.get('email')
        if email == self.context.get('user').email:
            self.add_error('email', 'You cannot add yourself as your subscriber/supervisor!')
        if not User.objects.filter(email=email).exists():
            self.add_error('email', 'User with this email does not exist.')
        return self.cleaned_data


class AddSupervisorForm(BaseSupervisionForm):
    email = forms.EmailField(label='Subscribe me to:')


class AddSubscriberForm(BaseSupervisionForm):
    email = forms.EmailField(label='Send invitation to:')


class KeyboardForm(forms.Form):
    keyboard_size = forms.ChoiceField(widget=forms.Select(), choices=KEYBOARD_CHOICES, initial=49)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(KeyboardForm, self).__init__(*args, **kwargs)


class DashboardExerciseForm(ExerciseForm):
    id = forms.CharField(widget=forms.TextInput(attrs={'readonly': 'readonly'}), required=False, label='ID')
    data = JSONField(widget=forms.HiddenInput)

    class Meta:
        model = Exercise
        exclude = ['authored_by']
        widgets = {
            'data': PrettyJSONWidget(attrs={'initial': 'parsed'}),
            'id': forms.TextInput(attrs={'readonly': 'readonly'}),
        }

    def __init__(self, disable_fields=False, *args, **kwargs):
        super(DashboardExerciseForm, self).__init__(*args, **kwargs)
        if disable_fields:
            for field in self.fields:
                self.fields.get(field).disabled = True


class TransposeRequestsField(forms.CharField):
    def to_python(self, value):
        value = super(TransposeRequestsField, self).to_python(value)
        if not value:
            return []
        return value.replace(' ', '').split(',')

    def prepare_value(self, value):
        if value is None:
            return

        value = super(TransposeRequestsField, self).prepare_value(value)
        if isinstance(value, str):
            return value
        return ','.join(value)


class DashboardPlaylistForm(PlaylistForm):
    transpose_requests = TransposeRequestsField(label='Transposition Requests', required=False)

    class Meta(PlaylistForm.Meta):
        exclude = ['id', 'authored_by']

    def __init__(self, disable_fields=False, *args, **kwargs):
        super(DashboardPlaylistForm, self).__init__(*args, **kwargs)
        if disable_fields:
            for field in self.fields:
                self.fields.get(field).disabled = True


class DashboardCourseForm(CourseForm):
    class Meta(CourseForm.Meta):
        exclude = ['id', 'authored_by']
