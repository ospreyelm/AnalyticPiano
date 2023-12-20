import json
from dateutil import parser
from datetime import datetime
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.postgres.forms import JSONField
from django.core.validators import FileExtensionValidator
from prettyjson import PrettyJSONWidget
from django.db.models import Q, Prefetch
from django.forms.models import ModelMultipleChoiceField
from django.core.serializers.json import DjangoJSONEncoder


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
    email = forms.EmailField(label="Email:")


class AddSubscriberForm(BaseSupervisionForm):
    email = forms.EmailField(label="Email:")


class AddConnectionForm(BaseSupervisionForm):
    email = forms.EmailField(label="Email:")


class RemoveSubscriptionConfirmationForm(forms.Form):
    CONFIRMATION_PHRASE = "remove this subscriber"
    # do not offer this option on the frontend but leave it here in case of bugs

    confirmation_text = forms.CharField(label="")

    def clean_confirmation_text(self):
        if self.cleaned_data["confirmation_text"] not in [
            self.CONFIRMATION_PHRASE,
            self.context.get("email"),
        ]:
            raise forms.ValidationError("Wrong value.")
        return self.cleaned_data["confirmation_text"]


class RemoveConnectionConfirmationForm(forms.Form):
    CONFIRMATION_PHRASE = "remove this connection"
    # do not offer this option on the frontend but leave it here in case of bugs

    confirmation_text = forms.CharField(label="")

    def clean_confirmation_text(self):
        if self.cleaned_data["confirmation_text"] not in [
            self.CONFIRMATION_PHRASE,
            self.context.get("email"),
        ]:
            raise forms.ValidationError(
                "Text does not match. Removal of this contact abandoned."
            )
        return self.cleaned_data["confirmation_text"]


class KeyboardForm(forms.Form):
    auto_advance = forms.BooleanField(
        required=False,
        initial=False,  # irrelevant due to default user preferences
    )

    auto_repeat = forms.BooleanField(
        required=False,
        initial=False,  # irrelevant due to default user preferences
    )

    auto_advance_delay = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 60, "min": 0}),
        label_suffix=" in seconds:",
        initial=2,  # irrelevant due to default user preferences
    )

    auto_repeat_delay = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 60, "min": 0}),
        label_suffix=" in seconds:",
        initial=2,  # irrelevant due to default user preferences
    )

    auto_sustain_duration = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 300, "min": 5}),
        label_suffix=" in tenths of a second:",
        initial=2,  # irrelevant due to default user preferences
    )

    keyboard_size = forms.ChoiceField(
        widget=forms.Select(),
        choices=KEYBOARD_CHOICES,
        initial=DEFAULT_KEYBOARD_SIZE,  # irrelevant due to default user preferences
    )

    keyboard_octaves_offset = forms.IntegerField(
        widget=forms.NumberInput(attrs={"step": 1, "max": 3, "min": -1}),
        initial=0,  # irrelevant due to default user preferences
        # when this value is +3, the top 13 keys of an 88-key piano will not work
        # minimum is set to -1 because -2 and lower cause a misrendering of the 88-key piano
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


class ManyWidget(forms.widgets.SelectMultiple):
    template_name = "../templates/dashboard/manywidget.html"
    option_template_name = "../templates/dashboard/manywidgetoption.html"

    def __init__(
        self, attrs=None, order_input=False, order_attr=None, additional_fields=[]
    ):
        self.attrs = attrs
        self.order_attr = order_attr
        self.order_input = order_input
        self.additional_fields = additional_fields
        super().__init__(attrs)

    def format_value(self, value):
        return value

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["order_attr"] = self.order_attr
        context["widget"]["order_input"] = self.order_input
        context["widget"]["additional_fields"] = self.additional_fields
        return context


class ManyField(ModelMultipleChoiceField):
    value = None

    def __init__(
        self,
        widget=ManyWidget,
        queryset=None,
        through_vals=None,
        format_title=str,
        order_attr=None,
        # additional fields in the M2M through table
        additional_fields=None,
        # processes the through_table data before rendering
        through_prepare=None,
    ):
        widget_inputs = {}
        self.queryset = queryset
        self.through_vals = through_vals
        self.format_title = format_title
        self.order_attr = order_attr
        self.through_prepare = through_prepare
        if self.order_attr:
            widget_inputs["order_attr"] = self.order_attr
            widget_inputs["order_input"] = True
        self.additional_fields = additional_fields
        if self.additional_fields:
            widget_inputs["additional_fields"] = self.additional_fields
        self.widget = widget(**widget_inputs)

        super().__init__(queryset=self.queryset)

    # This function is used for preparing both options and values, and for translating widget value into a python dict
    # TODO: this function should not do all of this!! Although it appears to be a Django flaw: it DOES do all of this within the exemplar ModelMultipleChoiceField.
    def prepare_value(self, value):
        # If the value is being submitted, meaning it came from the JSONified input value
        if type(value) is str:
            value = json.loads(value)
            value = list(map(lambda value_list: (value_list[0], value_list[2]), value))
        # this handles list of models for field value
        elif type(value) is list:
            # When an error occurs in the form, it returns the JSONified data as the only entry of a list, which we check for here
            #   instead of passing the JSON right back, we parse and re-dump because we want to use DjangoJSONEncoder
            if len(value) == 1 and isinstance(value[0], str):
                value = [json.loads(ele) for ele in value][0]
            else:
                value = list(
                    map(
                        lambda instance: [
                            self.prepare_value(instance),
                            self.label_from_instance(instance),
                            # gets this instance from self.values, pulls the prefetched through-table instance (which only self.values has), and adds its attributes to the tuple
                            list(
                                self.value.filter(id=instance.id)
                                .first()
                                ._prefetched_objects_cache.values()
                            )[0].first()
                            if self.value
                            else {},
                        ],
                        value,
                    )
                )
            if self.order_attr != None:
                # sorts the values by the through-table's order_attr
                value = sorted(
                    value,
                    key=lambda value_list: getattr(value_list[2], self.order_attr, ""),
                )
            for value_list in value:
                # if there isn't a through table instance associated with this, don't look for its attributes
                if type(value_list[2]) != dict:
                    value_list[2] = value_list[2].__dict__
                    if self.through_prepare:
                        value_list[2] = self.through_prepare(value_list[2])
                    # prevents things like ids from getting through
                    # TODO: this kind of filtering needs to be done upon form receipt too, to prevent users from editing ids and doing weird stuff
                    allowed_fields = []
                    if self.additional_fields:
                        allowed_fields += [
                            field["attr_name"] for field in self.additional_fields
                        ]
                    if self.order_attr:
                        allowed_fields += [self.order_attr]
                    value_list[2] = {
                        field_name: value_list[2][field_name]
                        for field_name in allowed_fields
                    }
                value_list[2] = json.dumps(value_list[2], cls=DjangoJSONEncoder)
        # this handles individual models within field options
        elif value is not None:
            value = value.pk
        else:
            value = list()
        return value

    def label_from_instance(self, obj):
        return self.format_title(obj)

    def clean(self, value):
        return self.prepare_value(value[0])


class DashboardPlaylistForm(PlaylistForm):
    editable_fields = ["is_public"]

    exercises = ManyField(
        order_attr="order",
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
        self.fields["exercises"].value = Exercise.objects.none()
        if self.instance.pk != None:
            # Replace the exercises field value with the exercises combined with the respective EPO
            self.fields["exercises"].value = self.instance.exercises.prefetch_related(
                # We use Prefetch and its queryset functionality to only prefetch the EPO for this playlist
                Prefetch(
                    "exerciseplaylistordered_set",
                    queryset=ExercisePlaylistOrdered.objects.filter(
                        playlist=self.instance
                    ),
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

    def clean(self):
        self.cleaned_data["exercises"] = [
            (Exercise.objects.get(pk=value_pair[0]), value_pair[1])
            for value_pair in self.cleaned_data["exercises"]
        ]
        return super().clean()

    def save(self, commit=True):
        self.instance.authored_by = self.context["user"]
        playlist = super(DashboardPlaylistForm, self).save(commit=commit)

        return playlist


course_date_format = "%d/%m/%Y"


class DashboardCourseForm(CourseForm):
    visible_to = ManyField()
    playlists = ManyField(
        order_attr="order",
        additional_fields=[
            {
                "attr_name": "publish_date",
                "placeholder": PlaylistCourseOrdered._meta.get_field(
                    "publish_date"
                ).verbose_name
                + " (DD/MM/YYYY)",
            },
            {
                "attr_name": "due_date",
                "placeholder": PlaylistCourseOrdered._meta.get_field(
                    "due_date"
                ).verbose_name
                + " (DD/MM/YYYY)",
            },
        ],
        # this function is passed to ManyField's `prepare_value` to render dates properly
        through_prepare=lambda through_values: {
            **through_values,
            "publish_date": through_values["publish_date"].strftime(course_date_format)
            if through_values["publish_date"]
            else None,
            "due_date": through_values["due_date"].strftime(course_date_format)
            if through_values["due_date"]
            else None,
        },
    )

    class Meta(CourseForm.Meta):
        fields = [
            "id",
            "title",
            "is_public",
            "open",
            "timely_credit",
            "tardy_credit",
            "late_credit",
            "tardy_threshold",
            "visible_to",
            "playlists",
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(DashboardCourseForm, self).__init__(*args, **kwargs)
        self.fields["visible_to"].queryset = Group.objects.filter(manager=user)
        self.fields["playlists"].queryset = Playlist.objects.filter(
            Q(authored_by=user) | Q(is_public=True)
        )

        if self.instance.pk != None:
            self.fields["visible_to"].queryset = self.fields[
                "visible_to"
            ].queryset.difference(self.instance.visible_to.all())
            # Replace the exercises field value with the exercises combined with the respective EPO
            self.fields["playlists"].value = self.instance.playlists.prefetch_related(
                # We use Prefetch and its queryset functionality to only prefetch the EPO for this playlist
                Prefetch(
                    "playlistcourseordered_set",
                    queryset=PlaylistCourseOrdered.objects.filter(course=self.instance),
                )
            ).order_by("playlistcourseordered__order")

    def clean(self):
        visible_to_ids = list(
            map(lambda value_pair: value_pair[0], self.cleaned_data["visible_to"])
        )
        self.cleaned_data["visible_to"] = Group.objects.filter(pk__in=visible_to_ids)

        self.cleaned_data["playlists"] = [
            (Playlist.objects.get(pk=value_pair[0]), value_pair[1])
            for value_pair in self.cleaned_data["playlists"]
        ]
        for value_pair in self.cleaned_data["playlists"]:
            if (
                "publish_date" in value_pair[1]
                and value_pair[1]["publish_date"] is not None
            ):
                try:
                    value_pair[1]["publish_date"] = datetime.strptime(
                        value_pair[1]["publish_date"], course_date_format
                    )
                except:
                    self.add_error(
                        "playlists",
                        f"Invalid publish date '{value_pair[1]['publish_date']}'",
                    )
                    value_pair[1]["publish_date"] = None
            if "due_date" in value_pair[1] and value_pair[1]["due_date"] is not None:
                try:
                    value_pair[1]["due_date"] = datetime.strptime(
                        value_pair[1]["due_date"], course_date_format
                    )
                except:
                    self.add_error(
                        "playlists", f"Invalid due date '{value_pair[1]['due_date']}'"
                    )
                    value_pair[1]["due_date"] = None
        return super().clean()

    def save(self, commit=True):
        self.instance.authored_by = self.context["user"]
        course = super(CourseForm, self).save(commit=commit)
        return course


class BaseDashboardGroupForm(forms.ModelForm):
    members = ManyField()

    class Meta:
        model = Group
        fields = ("name", "members")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.fields["members"].queryset = User.objects.filter(
            pk__in=user.performance_permits
        )
        if self.instance.pk != None:
            self.fields["members"].queryset = self.fields[
                "members"
            ].queryset.difference(self.instance.members.all())

    def clean(self):
        self.cleaned_data["members"] = User.objects.filter(
            pk__in=[value_pair[0] for value_pair in self.cleaned_data["members"]]
        )
        return super().clean()

    def save(self, commit=True):
        self.instance.manager = self.context["user"]
        group = super(BaseDashboardGroupForm, self).save(commit=commit)
        group.members.set(self.cleaned_data["members"])
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
