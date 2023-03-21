from django import forms
from django.contrib.auth import get_user_model
from django.contrib.postgres.forms import JSONField
from django.core.validators import FileExtensionValidator
from prettyjson import PrettyJSONWidget
from django.db.models import Q, Prefetch


from apps.accounts.models import KEYBOARD_CHOICES, DEFAULT_KEYBOARD_SIZE, Group
from apps.dashboard.fields import MultiDateField
from apps.exercises.forms import ExerciseForm, PlaylistForm, CourseForm
from apps.exercises.models import (
    Exercise,
    Playlist,
    PlaylistCourseOrdered,
    ExercisePlaylistOrdered,
)

import re

User = get_user_model()


class BaseSupervisionForm(forms.Form):
    def clean(self):
        email = self.cleaned_data.get("email")
        try:
            email = email.lower()
        except:
            self.add_error(
                "email", "The email input could not be parsed as a text string."
            )
        if email == self.context.get("user").email:
            self.add_error(
                "email",
                "This is your own email address! Enter the email of another user.",
            )
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
        if self.cleaned_data["confirmation_text"] not in [
            self.CONFIRMATION_PHRASE,
            self.context.get("email"),
        ]:
            raise forms.ValidationError("Wrong value.")
        return self.cleaned_data["confirmation_text"]


class KeyboardForm(forms.Form):
    keyboard_size = forms.ChoiceField(
        widget=forms.Select(), choices=KEYBOARD_CHOICES, initial=DEFAULT_KEYBOARD_SIZE
    )

    auto_advance = forms.BooleanField(required=False, initial=False)

    auto_advance_delay = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 60, "min": 0}),
        label_suffix=" (seconds):",
        initial=4,
    )

    auto_repeat = forms.BooleanField(required=False, initial=False)

    auto_repeat_delay = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 60, "min": 0}),
        label_suffix=" (seconds):",
        initial=6,
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(KeyboardForm, self).__init__(*args, **kwargs)


class DashboardExerciseForm(ExerciseForm):
    id = forms.CharField(
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
        required=False,
        label="ID",
    )

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


TRANSPOSE_SELECT_CHOICES = (
    ("", "[add by key signature]"),
    ("Gb", "7 flats"),
    ("Cb", "6 flats"),
    ("Db", "5 flats"),
    ("Ab", "4 flats"),
    ("Eb", "3 flats"),
    ("Bb", "2 flats"),
    ("F", "1 flat"),
    ("C", "0 flats or sharps"),  # bug
    ("G", "1 sharp"),
    ("D", "2 sharps"),
    ("A", "3 sharps"),
    ("E", "4 sharps"),
    ("B", "5 sharps"),
    ("F#", "6 sharps"),
    ("C#", "7 sharps"),
)


class CustomTransposeWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        self.attrs = attrs
        widgets = (
            forms.TextInput,
            forms.Select(
                choices=TRANSPOSE_SELECT_CHOICES, attrs={"style": "margin-left:16px"}
            ),
        )
        super(CustomTransposeWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        return [value, ""]

    def value_from_datadict(self, data, files, name):
        text, added = super().value_from_datadict(data, files, name)
        return text + (" " + added if not added in text else "")


# Widget used to display end edit m2m relations
# Inputs:
#   model: the type of model being displayed within the widget
#   model_format: a function converting a model instance into a string
#   value_attr: the attribute of the model used as its value within the form


class ManyWidget(forms.widgets.ChoiceWidget):
    template_name = "../templates/dashboard/manywidget.html"
    option_template_name = "../templates/dashboard/manywidgetoption.html"

    def __init__(self, attrs=None, order_input=True):
        self.attrs = attrs
        self.order_input = order_input
        super().__init__(attrs)

    def format_value(self, value):
        return value

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["order_input"] = self.order_input
        return context


class ManyField(forms.ModelMultipleChoiceField):
    value = None

    def __init__(
        self,
        widget=ManyWidget,
        queryset=None,
        through_vals=None,
        format_title=str,
        order_attr="order",
    ):
        self.widget = widget
        self.queryset = queryset
        self.through_vals = through_vals
        self.format_title = format_title
        self.order_attr = order_attr
        super().__init__(queryset=self.queryset)

    # This function is used for preparing both options and values
    def prepare_value(self, value):
        # this handles list of models for field value
        if type(value) is list:
            return list(
                map(
                    lambda instance: (
                        self.prepare_value(instance),
                        self.label_from_instance(instance),
                    ),
                    value,
                )
            )
        # this handles individual models within field options
        return value._id

    def label_from_instance(self, obj):
        return self.format_title(obj)

    def clean(self, value):
        print(value)
        return super().clean(value)


class DashboardPlaylistForm(PlaylistForm):

    editable_fields = ["is_public"]

    exercises = ManyField(
        queryset=None,
        widget=ManyWidget,
        format_title=lambda ex: ex.id
        + (f"- {ex.description}" if ex.description else ""),
    )

    class Meta(PlaylistForm.Meta):
        exclude = ["authored_by"]
        widgets = {
            "id": forms.TextInput(attrs={"readonly": "readonly"}),
            "is_auto": forms.CheckboxInput(attrs={"disabled": "disabled"}),
            "authored_by": forms.TextInput(attrs={"readonly": "readonly"}),
        }

    def __init__(self, disable_fields=False, *args, **kwargs):
        user = kwargs.pop("user")
        super(DashboardPlaylistForm, self).__init__(*args, **kwargs)
        # Since the queryset and through_vals are dependent on variable user and instance, set them with initialization inputs
        self.fields["exercises"].queryset = Exercise.objects.filter(
            Q(authored_by=user) | Q(is_public=True)
        )
        # Replace the exercises field value with the exercises combined with the respective EPO
        self.fields["exercises"].value = self.instance.exercises.prefetch_related(
            # We use Prefetch and its queryset functionality to only prefetch the EPO for this playlist
            Prefetch(
                "exerciseplaylistordered_set",
                queryset=ExercisePlaylistOrdered.objects.filter(playlist=self.instance),
            )
        ).order_by("exerciseplaylistordered__order")

        if disable_fields:
            for field in self.fields:
                if field not in self.editable_fields:
                    self.fields.get(field).disabled = True

    id = forms.CharField(
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
        required=False,
        label="ID",
    )

    transpose_requests = TransposeRequestsField(
        label="Keys for transposition",
        required=False,
        help_text="List of keys, case-sensitive and space-separated",
        # help_text="A list of keys, separated by spaces, which the playlist will be transposed to. Upper case letters for major, lower case for minor. Only the key signature matters, meaning that 'A f# Db' has the same result as 'f# A bb'. The key signature in the dropdown will be added to the ones in the text box upon saving.",
        widget=CustomTransposeWidget,
    )


class DashboardCourseForm(CourseForm):
    class Meta(CourseForm.Meta):
        fields = ["title", "playlists", "visible_to", "is_public", "open"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(DashboardCourseForm, self).__init__(*args, **kwargs)
        self.fields["playlists"].queryset = Playlist.objects.filter(
            Q(authored_by=user) | Q(is_public=True)
        )
        self.fields["playlists"].through_vals = PlaylistCourseOrdered.objects.filter(
            course=self.instance
        )

    playlists = ManyField()


class BaseDashboardGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ("name", "members")

    custom_m2m_fields = ["members"]
    custom_m2m_config = {
        "members": {"ordered": False},
    }

    def save(self, commit=True):
        self.instance.manager = self.context["user"]
        group = super(BaseDashboardGroupForm, self).save(commit=commit)
        return group


class DashboardGroupAddForm(BaseDashboardGroupForm):
    def __init__(self, *args, **kwargs):
        super(DashboardGroupAddForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        if Group.objects.filter(
            manager=self.context["user"], name=self.cleaned_data["name"]
        ).exists():
            raise forms.ValidationError("Group with this name already exists.")
        return self.cleaned_data["name"]


class DashboardGroupEditForm(BaseDashboardGroupForm):
    def __init__(self, *args, **kwargs):
        super(DashboardGroupEditForm, self).__init__(*args, **kwargs)


# def clean_name(self):
#     if (
#         Group.objects.exclude(id=self.context["group_id"])
#         .filter(manager=self.context["user"], name=self.cleaned_data["name"])
#         .exists()
#     ):
#         raise forms.ValidationError("Group with this name already exists.")
#     return self.cleaned_data["name"]


class ContentImportForm(forms.Form):
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=["csv"])],
        widget=forms.FileInput(attrs={"accept": ".csv"}),
    )
