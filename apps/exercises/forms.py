import re
import datetime
from copy import deepcopy
from ckeditor.widgets import CKEditorWidget
from django import forms
from prettyjson import PrettyJSONWidget

from apps.exercises.models import Exercise, Playlist, PerformanceData, Course


class ExpansiveForm(forms.ModelForm):
    EXPANSIVE_FIELD = None
    EXPANSIVE_FIELD_MODEL = None
    EXPANSIVE_FIELD_INITIAL = None

    def clean(self):
        super(ExpansiveForm, self).clean()
        self.expand()

    def expand(self):
        assert self.EXPANSIVE_FIELD is not None
        assert self.EXPANSIVE_FIELD_MODEL is not None
        assert self.EXPANSIVE_FIELD_INITIAL is not None

        expansive_field_data = re.sub(
            r"[^a-zA-Z0-9-,; \n]",
            "",
            self.cleaned_data.get(self.EXPANSIVE_FIELD, "").rstrip(","),
        )
        parsed_input = [
            n.upper().strip() for n in re.split("-*[,; \n]+-*", expansive_field_data)
        ]

        # to test if item exists
        all_object_ids = list(
            self.EXPANSIVE_FIELD_MODEL.objects.values_list("id", flat=True)
        )

        object_ids = []
        for string in parsed_input:
            if "-" in string:
                id_range = string
                for _id in self._expand_range(id_range, all_object_ids):
                    # ^ returns only items authored by the user
                    # ^ _id already verified
                    object_ids.append(_id)
            else:

                _id = string

                if len(_id) <= 6:
                    _id = f"{self.EXPANSIVE_FIELD_MODEL.zero_padding[:-len(_id)]}{_id}"

                if _id == "":
                    continue
                if _id not in all_object_ids:
                    # generate WARNING
                    continue

                item_is_public = (
                    self.EXPANSIVE_FIELD_MODEL.objects.get(id=_id).is_public == True
                )

                if item_is_public:
                    object_ids.append(_id)
                    continue

                user_authored_objects = list(
                    self.EXPANSIVE_FIELD_MODEL.objects.filter(
                        authored_by_id=self.context.get("user").id
                    ).values_list("id", flat=True)
                )

                if _id in user_authored_objects:
                    object_ids.append(_id)

        JOIN_STR = " "  # r'[,; \n]+'
        self.cleaned_data.update({self.EXPANSIVE_FIELD: JOIN_STR.join(object_ids)})

    def _integer_from_id(self, ex_str):
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        digits = "0123456789"
        reverse_str = ex_str[::-1]
        integer = 0
        base = 1
        for i in range(len(reverse_str)):
            char = reverse_str[i]
            if char in letters:
                integer += base * letters.index(char)
                base *= 26
            elif char in digits:
                integer += base * digits.index(char)
                base *= 10
            else:
                return None
        return integer

    def _id_from_integer(self, num):
        # must accord with models.py (do not make format changes)
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        reverse_id = ""
        bases = [26, 26, 10, 10, 26]
        for base in bases:
            if base == 26:
                reverse_id += letters[num % base]
            elif base == 10:
                reverse_id += str(num % base)
            num //= base
        if num != 0 or len(reverse_id) != len(bases):
            return None
        reverse_id += self.EXPANSIVE_FIELD_INITIAL
        return reverse_id[::-1]

    def _expand_range(self, id_range, all_object_ids, allowance=100):
        user_authored_objects = list(
            self.EXPANSIVE_FIELD_MODEL.objects.filter(
                authored_by_id=self.context.get("user").id
            )
            .values_list("id", flat=True)
            .order_by("id")
        )

        object_ids = []

        split_input = re.split("-+", id_range)
        if len(split_input) >= 2:
            lower = self._integer_from_id(split_input[0])
            upper = self._integer_from_id(split_input[-1])
            if lower is None or upper is None:
                return object_ids
            if not lower < upper:
                return object_ids
            for num in range(lower, upper + 1):
                item = self._id_from_integer(num)
                if item is None or item == "":
                    continue
                if item not in all_object_ids:
                    # generate WARNING
                    continue
                    self.add_error(
                        field=self.EXPANSIVE_FIELD,
                        error=f"{self.EXPANSIVE_FIELD_MODEL._meta.verbose_name} with ID {item} does not exist.",
                    )
                if item in user_authored_objects and item is not None and item != "":
                    # self-authored exercises only
                    object_ids.append(item)
                    allowance += -1
                if allowance == 0:
                    # FIXME generate warning message
                    break

        return object_ids


# Taken from deprecated music_controls.js prompt form
def parse_visibility(visibility_pattern, instance):
    visibility_reqs = [x for x in re.sub("/[^satbo*-]/gi", "", visibility_pattern)]
    # the permitted characters above must correspond to the logical tests below
    if len(visibility_reqs) < 1:
        visibility_reqs = (["none"])
    newdata = deepcopy(instance.data)
    flsb = newdata["chord"] # flsb stood for visibility models "first, last, soprano, bass"

    # if len(visibility_reqs) >= 1:
    #     for i in range(len(flsb)):
    #         flsb[i]["hidden"] += flsb[i]["visible"]
    #         flsb[i]["hidden"].sort()
    #         flsb[i]["visible"] = []

    for i in range(len(flsb)):
        default_viz_label = "*"
        viz_label = visibility_reqs[i] if i < len(visibility_reqs) else default_viz_label
        if not viz_label:
            viz_label = default_viz_label
        if viz_label == "*":
            flsb[i]["visible"] += flsb[i]["hidden"]
            flsb[i]["hidden"] = []
            flsb[i]["visible"].sort()
        elif viz_label == "-":
            flsb[i]["hidden"] += flsb[i]["visible"]
            flsb[i]["visible"] = []
            flsb[i]["hidden"].sort()
        else:
            flsb[i]["hidden"] += flsb[i]["visible"]
            flsb[i]["hidden"].sort()
            flsb[i]["visible"] = []
            if viz_label == "b":
                flsb[i]["visible"] = (
                    flsb[i]["visible"] + [flsb[i]["hidden"].pop(0)]
                    if len(flsb[i]["hidden"]) > 0
                    else []
                )
            elif viz_label == "t":
                flsb[i]["visible"] = (
                    flsb[i]["visible"] + [flsb[i]["hidden"].pop(1)]
                    if len(flsb[i]["hidden"]) > 1
                    else []
                )
            elif viz_label == "a":
                flsb[i]["visible"] = (
                    flsb[i]["visible"] + [flsb[i]["hidden"].pop(-2)]
                    if len(flsb[i]["hidden"]) > 1
                    else []
                )
            elif viz_label == "s":
                flsb[i]["visible"] = (
                    flsb[i]["visible"] + [flsb[i]["hidden"].pop(-1)]
                    if len(flsb[i]["hidden"]) > 0
                    else []
                )
            elif viz_label == "o":
                flsb[i]["visible"] = (
                    flsb[i]["visible"] + [flsb[i]["hidden"].pop(0)] + [flsb[i]["hidden"].pop(-1)]
                    if len(flsb[i]["hidden"]) > 1
                    else []
                )
            flsb[i]["visible"].sort()

    if len(visibility_reqs) >= 0:
        newdata["chord"] = flsb
        return newdata
    else:
        return instance.data


def represent_visibility(instance): # Not good. What happens for two-to-one mappings?
    chord_data = instance.data["chord"]
    visibility_pattern = ""
    for chord in chord_data:
        num_visible = len(chord["visible"])
        num_hidden = len(chord["hidden"])
        if num_hidden == 0:
            visibility_pattern += "*"
        elif num_visible == 0:
            visibility_pattern += "-"
        elif num_visible == 1:
            if len(chord["hidden"]) >= 1 \
            and chord["visible"][0] >= chord["hidden"][-1]:
                visibility_pattern += "s"
            elif len(chord["hidden"]) >= 3 \
            and chord["visible"][0] >= chord["hidden"][-2]:
                visibility_pattern += "a"
            elif len(chord["hidden"]) >= 1 \
            and chord["visible"][0] <= chord["hidden"][0]:
                visibility_pattern += "b"
            elif len(chord["hidden"]) >= 3 \
            and chord["visible"][0] <= chord["hidden"][1]:
                visibility_pattern += "t"
            else: visibility_pattern += "?"
        elif num_visible == 2:
            if len(chord["hidden"]) >= 1 \
            and chord["visible"][-1] >= chord["hidden"][-1] \
            and chord["visible"][0] <= chord["hidden"][0]:
                visibility_pattern += "o"
            else: visibility_pattern += "?"
        else: visibility_pattern += "?"
        visibility_pattern += " "
    return visibility_pattern.strip()


class ExerciseForm(forms.ModelForm):
    TYPE_MATCHING = "matching"
    TYPE_ANALYTICAL = "analytical"
    TYPE_ANALYTICAL_PCS = "analytical_pcs"
    TYPE_FIGURED_BASS = "figured_bass"
    TYPE_FIGURED_BASS_PCS = "figured_bass_pcs"
    TYPE_CHOICES = (
        (TYPE_MATCHING, "Matching"),
        (TYPE_ANALYTICAL, "Analytical"),
        (TYPE_ANALYTICAL_PCS, "Analytical (with pitch class checking)"),
        (TYPE_FIGURED_BASS, "Figured Bass"),
        (TYPE_FIGURED_BASS_PCS, "Figured Bass (with pitch class checking)"),
    )

    DISTRIBUTION_KEYBOARD = "keyboard"
    DISTRIBUTION_CHORALE = "chorale"
    DISTRIBUTION_GRANDSTAFF = "grandStaff"
    DISTRIBUTION_LH = "LH"
    DISTRIBUTION_RH = "RH"
    DISTRIBUTION_KEYBOARD_RH_PREFERENCE = "keyboardPlusRHBias"
    DISTRIBUTION_KEYBOARD_LH_PREFERENCE = "keyboardPlusLHBias"

    DISTRIBUTION_CHOICES = (
        (DISTRIBUTION_KEYBOARD, "Keyboard"),
        (DISTRIBUTION_CHORALE, "Chorale"),
        (DISTRIBUTION_GRANDSTAFF, "Grand Staff"),
        (DISTRIBUTION_LH, "Lower staff"),
        (DISTRIBUTION_RH, "Upper staff"),
        (DISTRIBUTION_KEYBOARD_LH_PREFERENCE, "Keyboard with lower staff bias"),
        (DISTRIBUTION_KEYBOARD_RH_PREFERENCE, "Keyboard with upper staff bias"),
    )

    intro_text = forms.CharField(
        widget=CKEditorWidget(config_name="limited"),
        required=False,
        help_text="Text showed to users before the exercise.",
    )
    # review_text = forms.CharField(widget=CKEditorWidget(config_name="safe"), required=False)
    type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        help_text="Assessment method for the user input. Matching means pitches must exactly match, analytical means that chords must satisfy the analysis displayed, with the same bass, and figured bass means the performance must be in the same register. Pitch class checking indicates pitch errors to the user via colored noteheads.",
    )
    staff_distribution = forms.ChoiceField(
        choices=DISTRIBUTION_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        help_text="The staff or staves that the notes will be displayed on. Bias affects the break point and the favored staff for single pitches in the mid-range.",
    )
    time_signature = forms.CharField(
        required=False,
        help_text="Enter a numerical time signature: two numbers separated by a slash."
    )
    visibility_pattern = forms.CharField(
        required=False,
        help_text="Visibility pattern of each chord: * for all pitches, - for none, s for soprano, b for bass.",
    )

    field_order = [
        "id",
        "description",
        "is_public",
        "rhythm",
        "visibility_pattern",
        "time_signature",
        "intro_text",
        "type",
        "staff_distribution",
    ]

    def __init__(self, *arg, **kwargs):
        super(ExerciseForm, self).__init__(*arg, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["intro_text"].initial = self.instance.data.get(
                "introText", None
            )
            # self.fields['review_text'].initial = self.instance.data.get('reviewText', None)
            self.fields["type"].initial = self.instance.data.get(
                "type", self.TYPE_MATCHING
            )
            self.fields["staff_distribution"].initial = self.instance.data.get(
                "staffDistribution", self.DISTRIBUTION_KEYBOARD
            )
            self.fields["time_signature"].initial = self.instance.data.get(
                "timeSignature", None
            )
            self.fields["visibility_pattern"].initial = represent_visibility(
                self.instance
            )

    def save(self, commit=True):
        instance = super(ExerciseForm, self).save(commit)
        print(self.cleaned_data.get("visibility_pattern"))

        if instance:
            instance.data["introText"] = self.cleaned_data["intro_text"]
            # instance.data['reviewText'] = self.cleaned_data['review_text']
            instance.data["type"] = self.cleaned_data["type"]
            instance.data["staffDistribution"] = self.cleaned_data["staff_distribution"]
            if self.cleaned_data["time_signature"]:
                instance.data["timeSignature"] = self.cleaned_data["time_signature"]
            else:
                instance.data["timeSignature"] = ""
            print(instance.data["chord"])
            instance.data = parse_visibility(
                self.cleaned_data.get("visibility_pattern"), instance
            )
            print(instance.data["chord"])
            instance.authored_by = self.context.get("user")
            instance.clean()
            instance.save()

        return instance

    class Meta:
        model = Exercise
        fields = "__all__"
        widgets = {
            "data": PrettyJSONWidget(attrs={"initial": "parsed"}),
        }


class PlaylistForm(forms.ModelForm):
    # EXPANSIVE_FIELD = "exercises"
    # EXPANSIVE_FIELD_MODEL = Exercise
    # EXPANSIVE_FIELD_INITIAL = "E"

    transposition_type = forms.ChoiceField(
        choices=Playlist.TRANSPOSE_TYPE_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        help_text="Determines order of transposed exercises. Exercise Loop means that each exercise will have its transposed versions come after it successively. Playlist Loop means that the entire playlist will come in its original key, followed successively by the playlist's transposed versions.",
    )

    class Meta:
        model = Playlist
        exclude = []
        widgets = {
            "id": forms.TextInput(attrs={"readonly": "readonly"}),
            "is_auto": forms.CheckboxInput(attrs={"readonly": "readonly"}),
            "authored_by": forms.TextInput(attrs={"readonly": "readonly"}),
        }

    field_order = [
        "id",
        "name",
        "is_public",
        "is_auto",
        "transposition_type",
        "transpose_requests",
        "exercises",
    ]


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        exclude = ("performance_dict",)
        widgets = {
            # "visible_to":forms.CheckboxSelectMultiple()
        }


class PerformanceDataForm(forms.ModelForm):
    class Meta:
        model = PerformanceData
        exclude = []
        widgets = {
            "data": PrettyJSONWidget(),
            "playlist_performances": PrettyJSONWidget(),
        }
