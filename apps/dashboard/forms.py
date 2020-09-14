from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class AddSupervisorForm(forms.Form):
    email = forms.EmailField(label='Enter supervisor email:')


class AddSubscriberForm(forms.Form):
    email = forms.EmailField(label='Enter subscriber email:')
