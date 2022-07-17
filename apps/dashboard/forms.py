from django import forms
from django.contrib.auth import get_user_model
from django.contrib.postgres.forms import JSONField
from django.core.validators import FileExtensionValidator
from prettyjson import PrettyJSONWidget

from apps.accounts.models import KEYBOARD_CHOICES, DEFAULT_KEYBOARD_SIZE, Group
from apps.dashboard.fields import MultiDateField
from apps.exercises.forms import ExerciseForm, PlaylistForm, CourseForm
from apps.exercises.models import Exercise

import re

User = get_user_model()


class BaseSupervisionForm(forms.Form):
    def clean(self):
        email = self.cleaned_data.get("email").lower()
        if email == self.context.get("user").email:
            self.add_error("email", "This is your own email address! Enter the email of another user.")
        if not User.objects.filter(email=email).exists():
            self.add_error("email", "No user is registered with this email.")

        self.cleaned_data["email"] = email
        return self.cleaned_data


class AddSupervisorForm(BaseSupervisionForm):
    email = forms.EmailField(label="Subscribe me to:")


class AddSubscriberForm(BaseSupervisionForm):
    email = forms.EmailField(label="Send invitation to:")


class RemoveSubscriptionConfirmationForm(forms.Form):
    CONFIRMATION_PHRASE = "remove"

    confirmation_text = forms.CharField(label="")

    def clean_confirmation_text(self):
        if self.cleaned_data["confirmation_text"] not in [self.CONFIRMATION_PHRASE, self.context.get("email")]:
            raise forms.ValidationError("Wrong value.")
        return self.cleaned_data["confirmation_text"]


class KeyboardForm(forms.Form):
    keyboard_size = forms.ChoiceField(widget=forms.Select(), choices=KEYBOARD_CHOICES, initial=DEFAULT_KEYBOARD_SIZE)

    auto_advance = forms.BooleanField(required=False, initial=False)

    auto_advance_delay = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 60, "min": 0}), label_suffix=" (seconds):", initial=4
    )

    auto_repeat = forms.BooleanField(required=False, initial=False)

    auto_repeat_delay = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 60, "min": 0}), label_suffix=" (seconds):", initial=6
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(KeyboardForm, self).__init__(*args, **kwargs)


class DashboardExerciseForm(ExerciseForm):
    id = forms.CharField(widget=forms.TextInput(attrs={"readonly": "readonly"}), required=False, label="ID")

    # analysis_enabled = forms.BooleanField(label='Enable Analysis', required=False)
    # analysis_modes = forms.MultipleChoiceField(
    #     widget=forms.CheckboxSelectMultiple(),
    #     choices=Exercise.ANALYSIS_MODE_CHOICES
    # )

    # highlight_enabled = forms.BooleanField(label='Enable Highlight', required=False)
    # highlight_modes = forms.MultipleChoiceField(
    #     widget=forms.CheckboxSelectMultiple,
    #     choices=Exercise.HIGHLIGHT_MODE_CHOICES
    # )

    # data_fields = ['analysis', 'highlight']

    data = JSONField(widget=forms.HiddenInput)

    editable_fields = ["description", "is_public"]

    class Meta:
        model = Exercise
        exclude = ["authored_by", "locked"]
        widgets = {
            "data": PrettyJSONWidget(attrs={"initial": "parsed"}),
            "id": forms.TextInput(attrs={"readonly": "readonly"}),
        }

    def __init__(self, disable_fields=False, *args, **kwargs):
        super(DashboardExerciseForm, self).__init__(*args, **kwargs)
        if disable_fields:
            for field in self.fields:
                if field not in self.editable_fields:
                    self.fields.get(field).disabled = True

    #     if self.instance and self.instance.pk:
    #         self._init_data_modes()

    # def _init_data_modes(self):
    #     for field in self.data_fields:
    #         if field not in self.instance.data:
    #             break

    #         _field = self.instance.data[field]
    #         _field_modes = []
    #         for mode, val in _field['mode'].items():
    #             if val:
    #                 _field_modes.append(mode)
    #         self.fields[f'{field}_enabled'].initial = _field['enabled']
    #         self.fields[f'{field}_modes'].initial = _field_modes

    # def save(self, commit=True):
    #     instance = super(DashboardExerciseForm, self).save(commit)
    #     for field in self.data_fields:
    #         modes = self.cleaned_data.pop(f'{field}_modes', [])
    #         enabled = self.cleaned_data.pop(f'{field}_enabled', False)
    #         instance = instance.set_data_modes(modes=modes, enabled=enabled, field_name=field)
    #     return instance


class TransposeRequestsField(forms.CharField):
    def to_python(self, value):
        value = super(TransposeRequestsField, self).to_python(value)
        if not value:
            return []
        return re.split(r"[,; \n]+", value.strip())

    def prepare_value(self, value):
        if value is None:
            return

        value = super(TransposeRequestsField, self).prepare_value(value)
        if isinstance(value, str):
            return value
        TRANSP_JOIN_STR = " "  # r'[,; \n]+'
        return TRANSP_JOIN_STR.join(value)


class DashboardPlaylistForm(PlaylistForm):
    id = forms.CharField(widget=forms.TextInput(attrs={"readonly": "readonly"}), required=False, label="ID")

    transpose_requests = TransposeRequestsField(label="Transposition requests", required=False)

    editable_fields = ["is_public"]

    class Meta(PlaylistForm.Meta):
        exclude = ["authored_by"]
        widgets = {
            "exercises": forms.Textarea,
            "id": forms.TextInput(attrs={"readonly": "readonly"}),
            "is_auto": forms.CheckboxInput(attrs={"disabled": "disabled"}),
            "authored_by": forms.TextInput(attrs={"readonly": "readonly"}),
        }

    def __init__(self, disable_fields=False, *args, **kwargs):
        super(DashboardPlaylistForm, self).__init__(*args, **kwargs)
        if disable_fields:
            for field in self.fields:
                if field not in self.editable_fields:
                    self.fields.get(field).disabled = True


class DashboardCourseForm(CourseForm):
    publish_dates = MultiDateField(
        widget=forms.Textarea(
            attrs={"placeholder": "e.g. for a course with three playlists: 2021-09-30 2021-10-10 2021-10-17"}
        )
    )

    due_dates = MultiDateField(
        widget=forms.Textarea(
            attrs={"placeholder": "e.g. for a course with three playlists: 2021-09-30 2021-10-10 2021-10-17"}
        )
    )

    visible_to = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "multiselect"}),
        help_text="If no group is selected, course will be visible to all subscribers.",
    )

    class Meta(CourseForm.Meta):
        fields = ["title", "slug", "playlists", "publish_dates", "due_dates", "visible_to", "is_public"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(DashboardCourseForm, self).__init__(*args, **kwargs)
        self.fields["visible_to"].queryset = user.managed_groups.all()

    def clean_due_dates(self):
        if not self.cleaned_data["due_dates"]:
            return
        self._clean_multi_dates(dates=self.cleaned_data["due_dates"], playlists=self.cleaned_data["playlists"])
        return self.cleaned_data["due_dates"]

    def clean_publish_dates(self):
        if not self.cleaned_data["publish_dates"]:
            return
        self._clean_multi_dates(dates=self.cleaned_data["publish_dates"], playlists=self.cleaned_data["playlists"])
        return self.cleaned_data["publish_dates"]

    def _clean_multi_dates(self, dates, playlists):
        if dates and len(dates.split(" ")) != len(playlists.split(" ")):
            raise forms.ValidationError("Make sure the dates are set for either all or none of the playlists.")


class BaseDashboardGroupForm(forms.ModelForm):
    new_members = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Comma-separated emails of new members"}), required=False
    )

    class Meta:
        model = Group
        fields = ("name", "new_members")

    def clean_new_members(self):
        new_members_list = self.cleaned_data["new_members"].rstrip(",").replace(" ", "").split(",")
        new_members = list(
            self.context["user"].subscribers.filter(email__in=new_members_list).values_list("id", flat=True)
        )
        return new_members

    def save(self, commit=True):
        self.instance.manager = self.context["user"]
        group = super(BaseDashboardGroupForm, self).save(commit=True)
        group.add_members(self.cleaned_data["new_members"])
        return group


class DashboardGroupAddForm(BaseDashboardGroupForm):
    def __init__(self, *args, **kwargs):
        super(DashboardGroupAddForm, self).__init__(*args, **kwargs)
        self.fields["new_members"].label = "Members"

    def clean_name(self):
        if Group.objects.filter(manager=self.context["user"], name=self.cleaned_data["name"]).exists():
            raise forms.ValidationError("Group with this name already exists.")
        return self.cleaned_data["name"]


class DashboardGroupEditForm(BaseDashboardGroupForm):
    def clean_name(self):
        if (
            Group.objects.exclude(id=self.context["group_id"])
            .filter(manager=self.context["user"], name=self.cleaned_data["name"])
            .exists()
        ):
            raise forms.ValidationError("Group with this name already exists.")
        return self.cleaned_data["name"]


class ContentImportForm(forms.Form):
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=["csv"])],
        widget=forms.FileInput(attrs={"accept": ".csv"}),
    )
