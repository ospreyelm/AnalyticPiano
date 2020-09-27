from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.core.exceptions import ValidationError

User = get_user_model()


class UserAdminCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ('email','first_name','last_name',)


class CustomAuthenticationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'password')

    email = forms.CharField(widget=forms.TextInput(attrs={'autofocus': True}))
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )

    error_messages = {
        'invalid_login':
            "Please enter a correct %(username)s and password. Note that both "
            "fields may be case-sensitive."
        ,
        'inactive': "This account is inactive."
    }

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        user = authenticate(username=email, password=password)
        if user is None:
            raise ValidationError({'password': 'Invalid credentials.'})
        if not user.is_active:
            raise ValidationError({'email': 'This user is not active.'})
        return self.cleaned_data


class RegistrationForm(forms.ModelForm):
    # error_messages = {
    #     'password_mismatch': 'The two password fields didn’t match.',
    # }

    class Meta:
        model = User
        fields = ("email",)
        field_classes = {'email': UsernameField}
