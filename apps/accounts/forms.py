from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.core.exceptions import ValidationError

User = get_user_model()


class UserAdminCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("email",)


class CustomAuthenticationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email", "password")

    email = forms.CharField(widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )

    error_messages = {
        "invalid_login": "Please enter a correct email and password. The password " "is case-sensitive.",
        "inactive": "This account is inactive.",
    }

    def clean(self):
        email = self.cleaned_data.get("email").lower()
        password = self.cleaned_data.get("password")

        user = authenticate(username=email, password=password)
        if user is None:
            raise ValidationError({"password": "Invalid credentials."})
        if not user.is_active:
            raise ValidationError({"email": "This user is not active."})
        return {"email": email, "password": password}


class RegistrationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password", "confirm_password")
        field_classes = {"email": UsernameField}

    password = forms.CharField(
        label="Password",
        strip=True,
        widget=forms.PasswordInput,
    )

    confirm_password = forms.CharField(
        label="Confirm Password",
        strip=True,
        widget=forms.PasswordInput,
    )

    def clean(self):
        password = self.cleaned_data.get("password")
        confirm_password = self.cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise ValidationError({"confirm_password": "Passwords don't match."})

    def save(self, commit=True):
        return super(RegistrationForm, self).save(commit=commit)


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField()

    def clean(self):
        super(ForgotPasswordForm, self).clean()

        # applies .lower() to user input
        user = User.objects.filter(email=self.cleaned_data.get("email", "").lower()).first()
        if user is None:
            raise ValidationError({"email": " There is no registered user with this email."})

        if user.is_staff:
            raise ValidationError(
                {
                    "email": "This email belongs to an admin user. To reset the password, please proceed from the admin panel."
                }
            )

        user.send_forgotten_password()


class PreferredMuteValue(forms.Form):
    mute = forms.BooleanField(initial=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(PreferredMuteValue, self).__init__(*args, **kwargs)
