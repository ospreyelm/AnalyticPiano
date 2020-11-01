from django import forms
from django.contrib.auth import get_user_model
from apps.accounts.models import KEYBOARD_CHOICES

User = get_user_model()


class AddSupervisorForm(forms.Form):
    email = forms.EmailField(label='Enter supervisor email:')


class AddSubscriberForm(forms.Form):
    email = forms.EmailField(label='Enter subscriber email:')

class KeyboardForm(forms.Form):
    keyboard_size = forms.ChoiceField(widget=forms.Select(), choices=KEYBOARD_CHOICES, initial=49)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user',None)
        super(KeyboardForm, self).__init__(*args, **kwargs)

