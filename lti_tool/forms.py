from django import forms
from prettyjson import PrettyJSONWidget

from lti_tool.models import Exercise


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        exclude = []
        widgets = {
            'data': PrettyJSONWidget(),
        }
