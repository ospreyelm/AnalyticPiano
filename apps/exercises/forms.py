import re
import datetime
from copy import deepcopy
from ckeditor.widgets import CKEditorWidget
from django import forms
from prettyjson import PrettyJSONWidget

from apps.exercises.models import Exercise, Playlist, PerformanceData, Course
from django.utils.html import conditional_escape, format_html


class CollapsibleCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = "dashboard/widgets/collapsible_checkbox_select.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # We ensure the template knows how to handle the grouped structure
        return context

CONTENT_TAGS = [
    ("General Concepts", [
        ("intervals", "Intervals"),
        ("scales", "Scales"),
        ("triads", "Triads"),
        ("seventh-chords", "Seventh Chords"),
        ("voice-leading", "Voice Leading"),
        ("roman-numerals", "Roman Numerals"),
        ("secondary-dominants", "Secondary Dominants"),
        ("counterpoint", "Counterpoint"),
        ("harmonic-dictation", "Harmonic Dictation"),
        ("melodic-dictation", "Melodic Dictation"),
        ("sight-singing", "Sight Singing"),
        ("rhythm", "Rhythm"),
        ("bach", "Bach Chorales"),
    ]),
    
    ("Core Sequence (Tiers 1-5)", [
        ("unit:1", "Unit 1: Pitch & staff notation"),
        ("unit:2", "Unit 2: Rhythm & meter"),
        ("unit:3", "Unit 3: Scales & key signatures"),
        ("unit:4", "Unit 4: Intervals"),
        ("unit:5", "Unit 5: Triads & seventh chords"),
        ("unit:6", "Unit 6: Voice leading fundamentals"),
        ("unit:7", "Unit 7: Cadences"),
        ("unit:8", "Unit 8: Non-harmonic tones"),
        ("unit:9", "Unit 9: Tonic & dominant"),
        ("unit:10", "Unit 10: First inversions"),
        ("unit:11", "Unit 11: Pre-dominants"),
        ("unit:12", "Unit 12: Second inversions"),
        ("unit:13", "Unit 13: Rule of the octave"),
        ("unit:14", "Unit 14: Diatonic seventh chords"),
        ("unit:15", "Unit 15: Sequences"),
        ("unit:16", "Unit 16: Applied chords"),
        ("unit:17", "Unit 17: Modal mixture"),
        ("unit:18", "Unit 18: Neapolitan & aug. sixths"),
        ("unit:19", "Unit 19: Modulation I"),
        ("unit:20", "Unit 20: Modulation II"),
        ("unit:21", "Unit 21: Formal structures"),
        ("unit:22", "Unit 22: Sonata & rondo forms"),
        ("unit:23", "Unit 23: Enharmonic reinterpretation"),
        ("unit:24", "Unit 24: Chromatic mediants"),
        ("unit:25", "Unit 25: Omnibus progressions"),
        ("unit:26", "Unit 26: Extended tertian harmony"),
        ("unit:27", "Unit 27: Tonal paraphrase & dissolution"),
        ("unit:28", "Unit 28: Modal borrowing & exoticism"),
        ("unit:29", "Unit 29: Pitch-class sets I"),
        ("unit:30", "Unit 30: Pitch-class sets II"),
        ("unit:31", "Unit 31: Symmetry & inversional axes"),
        ("unit:32", "Unit 32: Twelve-tone serialism I"),
        ("unit:33", "Unit 33: Twelve-tone serialism II"),
        ("unit:34", "Unit 34: Diatonic modes"),
        ("unit:35", "Unit 35: Non-diatonic scales"),
        ("unit:36", "Unit 36: Rhythm & meter (post-tonal)"),
        ("unit:37", "Unit 37: Neo-Riemannian theory"),
        ("unit:38", "Unit 38: Spectralism & microtonality"),
        ("unit:39", "Unit 39: Minimalism & process music"),
        ("unit:40", "Unit 40: Textural analysis"),
        ("unit:41", "Unit 41: Jazz chord symbols & voicings"),
        ("unit:42", "Unit 42: ii–V–I & cadential patterns"),
        ("unit:43", "Unit 43: Blues harmony"),
        ("unit:44", "Unit 44: Jazz scales & modes"),
        ("unit:45", "Unit 45: Chord-scale theory"),
        ("unit:46", "Unit 46: Reharmonization"),
        ("unit:47", "Unit 47: Jazz form & improvisation"),
        ("unit:48", "Unit 48: Modal jazz"),
        ("unit:49", "Unit 49: Post-bop & free jazz"),
        ("unit:50", "Unit 50: Pop & rock harmony"),
        ("unit:51", "Unit 51: Film & functional harmony"),
    ]),
    
    ("Branch A: Figured Bass", [
        ("unit:A1", "Unit A1: Intro to thoroughbass"),
        ("unit:A2", "Unit A2: 6/3 chords (first inversion)"),
        ("unit:A3", "Unit A3: 6/4 chords (second inversion)"),
        ("unit:A4", "Unit A4: 7–6 suspensions"),
        ("unit:A5", "Unit A5: 4–3 suspensions"),
        ("unit:A6", "Unit A6: 2–3 bass suspensions"),
        ("unit:A7", "Unit A7: Dominant seventh (7 figure)"),
        ("unit:A8", "Unit A8: 6/5 chords"),
        ("unit:A9", "Unit A9: 4/2 chords"),
        ("unit:A10", "Unit A10: Ninths (9/8, 9/7, 9/4)"),
        ("unit:A11", "Unit A11: Double suspensions"),
        ("unit:A12", "Unit A12: Chromatic figures"),
        ("unit:A13", "Unit A13: Partial figuring"),
        ("unit:A14", "Unit A14: Keyboard realization"),
        ("unit:A15", "Unit A15: Figured bass → Roman numerals"),
    ]),

    ("Branch B: Partimenti", [
        ("unit:B1", "Unit B1: Formal clausulae"),
        ("unit:B2", "Unit B2: Simple cadence (2 parts)"),
        ("unit:B3", "Unit B3: Bass clausula & 3-part cadence"),
        ("unit:B4", "Unit B4: Alto clausula & 4-part cadence"),
        ("unit:B5", "Unit B5: Shorthand figures for 5/3"),
        ("unit:B6", "Unit B6: Diminution fundamentals"),
        ("unit:B7", "Unit B7: Ascending parallel tenths"),
        ("unit:B8", "Unit B8: Descending parallel tenths"),
        ("unit:B9", "Unit B9: Folia bass & variations"),
        ("unit:B10", "Unit B10: Syncopated diminution"),
        ("unit:B11", "Unit B11: Compound cadence (2 parts)"),
        ("unit:B12", "Unit B12: Compound cadence (3–4 parts)"),
        ("unit:B13", "Unit B13: Double cadence"),
        ("unit:B14", "Unit B14: Opening formulae"),
        ("unit:B15", "Unit B15: Hexachordal system"),
        ("unit:B16", "Unit B16: Half-step motion in bass"),
        ("unit:B17", "Unit B17: Rule of the octave (major)"),
        ("unit:B18", "Unit B18: Rule of the octave (minor)"),
        ("unit:B19", "Unit B19: Advanced rule of the octave"),
        ("unit:B20", "Unit B20: Partimenti I — stepwise bass"),
        ("unit:B21", "Unit B21: Partimenti II — leaping bass"),
        ("unit:B22", "Unit B22: Evaded & deceptive cadences"),
        ("unit:B23", "Unit B23: Three constraint systems"),
        ("unit:B24", "Unit B24: Lament bass & omnibus"),
        ("unit:B25", "Unit B25: Bariolage & arpeggiation"),
        ("unit:B26", "Unit B26: Double counterpoint"),
        ("unit:B27", "Unit B27: Imitation & sequences"),
        ("unit:B28", "Unit B28: Introduction to fugue"),
        ("unit:B29", "Unit B29: Fugue from partimento"),
        ("unit:B30", "Unit B30: Partimento as concerto"),
    ]),

    ("Branch C: Interval Cycles", [
        ("unit:C1", "Unit C1: Interval cycles 1–6"),
        ("unit:C2", "Unit C2: Cyclic collections"),
        ("unit:C3", "Unit C3: Transpositional symmetry"),
        ("unit:C4", "Unit C4: Slonimsky's Thesaurus overview"),
        ("unit:C5", "Unit C5: Interpolation"),
        ("unit:C6", "Unit C6: Ultrapolation & infrapolation"),
        ("unit:C7", "Unit C7: Combination cycles in analysis"),
        ("unit:C8", "Unit C8: Composition with interval & combination cycles"),
    ]),

    ("Branch D: Neo-Riemannian", [
        ("unit:D1", "Unit D1: P, L, R transformations"),
        ("unit:D2", "Unit D2: The Tonnetz"),
        ("unit:D3", "Unit D3: Compound transformations"),
        ("unit:D4", "Unit D4: Hexatonic & octatonic poles"),
        ("unit:D5", "Unit D5: NR analysis — 19th-century repertoire"),
        ("unit:D6", "Unit D6: Voice-leading geometry"),
        ("unit:D7", "Unit D7: NR and jazz"),
        ("unit:D8", "Unit D8: NR and post-tonal music"),
    ]),
]




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

    if not len(visibility_reqs) >= 0:
        # necessary as protection against type errors?
        return instance.data

    newdata = deepcopy(instance.data)
    flsb = newdata["chord"]
    # flsb stood for "first, last, soprano, bass"---the originally supported visibility models

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
            elif viz_label == "u":
                if len(flsb[i]["hidden"]) > 1:
                    flsb[i]["visible"] = flsb[i]["visible"] + flsb[i]["hidden"][1:]
                    flsb[i]["hidden"] = flsb[i]["hidden"][0:1]
                else:
                    pass
            flsb[i]["visible"].sort()

    newdata["chord"] = flsb
    return newdata

def represent_visibility(instance): # Not good. What happens for two-to-one mappings?
    # Check if this is a new CIR format (MusicXML import) or legacy format
    if "score" in instance.data:
        # New CIR format - no visibility pattern support yet
        return ""
    
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
            elif len(chord["hidden"]) == 1 \
            and chord["hidden"][0] <= chord["visible"][0]:
                visibility_pattern += "u"
            else: visibility_pattern += "?"
        else: visibility_pattern += "?"
        # visibility_pattern += " "
    return visibility_pattern.strip()


CHORALE_ANALYSIS_KEYS = [
    "abbreviate_thoroughbass",
    "note_names",
    "fixed_do",
    "scientific_pitch",
    "pitch_class",
    "spacing",
    "scale_degrees",
    "solfege",
    "do_based_solfege",
    "thoroughbass",
    "roman_numerals",
    "roman_numerals_exp",
    "chord_labels",
    "intervals",
    "intervals_wrap_after_octave",
    "intervals_wrap_after_octave_plus_ditone",
    "generic_intervals",
    "generic_intervals_wrap_after_octave",
    "generic_intervals_wrap_after_octave_plus_ditone",
    "pci",
    "set_class_set",
    "set_class_normal",
    "set_class_prime",
    "set_class_forte",
]


class ExerciseForm(forms.ModelForm):
    TYPE_CHORALE = "chorale"
    TYPE_CHORALE_IDENTIFICATION = "chorale_identification"
    TYPE_IDENTIFICATION = "identification"
    TYPE_MATCHING = "matching"
    TYPE_ANALYTICAL = "analytical"
    TYPE_ANALYTICAL_PCS = "analytical_pcs"
    TYPE_FIGURED_BASS = "figured_bass"
    TYPE_FIGURED_BASS_PCS = "figured_bass_pcs"
    TYPE_CHOICES = (
        (TYPE_MATCHING, "Exact match"),
        (TYPE_ANALYTICAL, "Analysis match"),
        (TYPE_ANALYTICAL_PCS, "Analysis match with wrong PCs highlighted"),
        (TYPE_FIGURED_BASS, "Figured bass"),
        (TYPE_FIGURED_BASS_PCS, "Figured bass with wrong PCs highlighted"),
    )

    IDENT_MODE_CHOICES = (
        ("submit", "Submit mode — student chooses all answers, then presses Submit to see results"),
        ("practice", "Practice mode — correct/incorrect shown immediately after each choice"),
        ("test", "Test mode — answers locked after choosing, no feedback shown"),
    )

    CHORALE_MODE_CHOICES = (
        ("play-all-voices", "Play all voices"),
        ("play-outer", "Play outer voices"),
        ("play-soprano", "Play soprano"),
        ("play-bass", "Play bass line"),
    )

    DISTRIBUTION_KEYBOARD = "keyboard"
    DISTRIBUTION_KEYBOARD_LH_PREFERENCE = "keyboardPlusLHBias"
    DISTRIBUTION_KEYBOARD_RH_PREFERENCE = "keyboardPlusRHBias"
    DISTRIBUTION_CHORALE = "chorale"
    DISTRIBUTION_GRANDSTAFF = "grandStaff"
    DISTRIBUTION_LH = "LH"
    DISTRIBUTION_RH = "RH"

    DISTRIBUTION_CHOICES = (
        (DISTRIBUTION_KEYBOARD, "Keyboard* or break solo lines at B4, C4"),
        (DISTRIBUTION_KEYBOARD_LH_PREFERENCE, "Keyboard* or break solo lines above F4"),
        (DISTRIBUTION_KEYBOARD_RH_PREFERENCE, "Keyboard* or break solo lines below G3"),
        (DISTRIBUTION_CHORALE, "Chorale or break solo lines at B4, C4"),
        (DISTRIBUTION_GRANDSTAFF, "Break at B4, C4"),
        (DISTRIBUTION_LH, "Lower staff only, legible through G4"),
        (DISTRIBUTION_RH, "Upper staff only, legible through F3"),
    )

    intro_text = forms.CharField(
        widget=CKEditorWidget(config_name="limited"),
        required=False,
        label="Prompt",
        # help_text="Prompt shown to users until the exercise is complete.",
    )
    # review_text = forms.CharField(widget=CKEditorWidget(config_name="safe"), required=False)
    type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        label="Assessment method",
        # help_text="Assessment method.",
    )
    staff_distribution = forms.ChoiceField(
        choices=DISTRIBUTION_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        help_text="You may need to refresh the page to edit this field more than once. *SAT no lower than G3, bass no higher than F3.",
    )
    time_signature = forms.CharField(
        required=False,
        help_text="Enter a numerical time signature: two numbers separated by a slash."
    )
    semibreves_per_line = forms.IntegerField(
        required=False,
        help_text="Fit this many semibreves across the page. Use this setting to avoid visual collisions in the analysis."
    )
    visibility_pattern = forms.CharField(
        required=False,
        help_text="Visibility pattern of each chord: * for all pitches, - for none, s for soprano, b for bass.",
    )
    chorale_mode = forms.ChoiceField(
        choices=CHORALE_MODE_CHOICES,
        required=False,
        label="Chorale mode",
        help_text="What the student is expected to perform.",
    )
    chorale_target_voices = forms.MultipleChoiceField(
        required=False,
        label="Graded voices",
        widget=forms.CheckboxSelectMultiple,
        help_text="Which voices the grader should require (default: all voices).",
    )
    chorale_visible_voices = forms.MultipleChoiceField(
        required=False,
        label="Visible voices",
        widget=forms.CheckboxSelectMultiple,
        help_text="Show or hide notation for individual voices in the score.",
    )
    chorale_label_mode = forms.ChoiceField(
        choices=(
            ("none", "Hide analysis"),
            ("note_names", "Note names"),
            ("figures", "Figured bass (full)"),
            ("figures_abbrev", "Figured bass (abbreviated)"),
            ("romans", "Roman numerals"),
            ("romans_exp", "Roman numerals (experimental)"),
        ),
        required=False,
        label="Analysis labels",
        widget=forms.RadioSelect(),
    )
    chorale_show_chord_labels = forms.BooleanField(
        required=False,
        label="Show chord symbols",
    )
    chorale_transpose = forms.IntegerField(
        required=False,
        label="Transpose (semitones)",
        help_text="Positive for up, negative for down. 0 keeps the original key.",
    )
    chorale_tempo = forms.IntegerField(
        required=False,
        label="Practice tempo (BPM)",
        min_value=20,
        help_text="Suggested tempo for the exercise viewport.",
    )
    chorale_wait_mode = forms.BooleanField(
        required=False,
        label="Wait for correct notes",
        help_text="If enabled, the viewport only advances when the player satisfies the current onset.",
    )
    chorale_show_notation = forms.BooleanField(
        required=False,
        label="Show notation",
        initial=True,
        help_text="Uncheck for 'Analysis Match' mode where the student plays from labels only.",
    )
    chorale_onset_window_ms = forms.IntegerField(
        required=False,
        label="Onset tolerance (ms)",
        min_value=10,
        help_text="How wide of a timing window to accept for attacks.",
    )
    chorale_release_tolerance_pct = forms.IntegerField(
        required=False,
        label="Release tolerance (%)",
        min_value=0,
        max_value=100,
        help_text="How much of the notated duration must be held before releasing.",
    )
    chorale_octave_flexible = forms.BooleanField(
        required=False,
        label="Allow octave displacement",
    )
    chorale_chord_member_min = forms.IntegerField(
        required=False,
        label="Minimum chord members",
        min_value=1,
        help_text="Require at least this many correct notes per onset (defaults to all).",
    )
    chorale_excerpt_start = forms.IntegerField(
        required=False,
        label="Excerpt start measure",
        min_value=0,
    )
    chorale_excerpt_end = forms.IntegerField(
        required=False,
        label="Excerpt end measure",
        min_value=0,
    )

    # ---- Identification-only fields ----
    ident_mode = forms.ChoiceField(
        choices=IDENT_MODE_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        label="Feedback mode",
        initial="submit",
        help_text="Controls when and whether the student sees correct/incorrect feedback.",
    )

    # ---- Interval-only fields ----
    compound_intervals = forms.BooleanField(
        required=False,
        label="Allow compound intervals",
        help_text="When checked, intervals larger than an octave are labeled as compound (10th, 12th, etc.). Default: reduce to within the octave.",
        initial=False,
    )

    tags = forms.MultipleChoiceField(
        choices=CONTENT_TAGS,
        widget=CollapsibleCheckboxSelectMultiple,
        required=False,
        label="Tags",
    )

    field_order = [
        "id",
        "description",
        "is_public",
        "tags",
        "rhythm",
        "visibility_pattern",
        "time_signature",
        "semibreves_per_line",
        "intro_text",
        "type",
        "staff_distribution",
        "chorale_mode",
        "chorale_target_voices",
        "chorale_visible_voices",
        "chorale_label_mode",
        "chorale_show_chord_labels",
        "chorale_transpose",
        "chorale_tempo",
        "chorale_wait_mode",
        "chorale_onset_window_ms",
        "chorale_release_tolerance_pct",
        "chorale_octave_flexible",
        "chorale_chord_member_min",
        "chorale_excerpt_start",
        "chorale_excerpt_end",
        "ident_mode",
        "compound_intervals",
        "data",
    ]

    def __init__(self, *arg, **kwargs):
        super(ExerciseForm, self).__init__(*arg, **kwargs)
        self._is_chorale = self._detect_chorale()
        self._is_chorale_identification = self._detect_chorale_identification()
        self._is_identification = self._detect_identification()
        self._chorale_voice_choices = []
        self._configure_type_field()
        if self.instance and self.instance.pk:
            self.fields["tags"].initial = list(self.instance.tags or [])
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
            self.fields["semibreves_per_line"].initial = self.instance.data.get(
                "semibrevesPerLine", None
            )
            self.fields["visibility_pattern"].initial = represent_visibility(
                self.instance
            )
        self._configure_chorale_fields()
        self._configure_identification_fields()
        self._configure_interval_fields()

    def save(self, commit=True):
        instance = super(ExerciseForm, self).save(commit)

        if instance:
            instance.data["introText"] = self.cleaned_data["intro_text"]
            # instance.data['reviewText'] = self.cleaned_data['review_text']
            instance.data["type"] = self.cleaned_data["type"]
            instance.data["staffDistribution"] = self.cleaned_data["staff_distribution"]
            if self.cleaned_data["time_signature"]:
                instance.data["timeSignature"] = self.cleaned_data["time_signature"]
            else:
                instance.data["timeSignature"] = ""
            instance.data["semibrevesPerLine"] = self.cleaned_data["semibreves_per_line"]
            if not self._is_chorale and "chord" in instance.data:
                instance.data = parse_visibility(
                    self.cleaned_data.get("visibility_pattern"), instance
                )
            instance.authored_by = self.context.get("user")
            instance.clean()
            if self._is_chorale:
                self._store_chorale_settings(instance)
            if self._is_identification:
                self._store_identification_settings(instance)
            if self._detect_interval():
                self._store_interval_settings(instance)
            instance.save()

        return instance

    class Media:
        css = {"all": ("css/admin_chorale.css",)}

    class Meta:
        model = Exercise
        fields = "__all__"
        widgets = {
            "data": PrettyJSONWidget(attrs={"initial": "parsed"}),
        }

    # --------------------
    # Chorale helpers
    # --------------------

    CHORALE_ONLY_FIELDS = [
        "chorale_mode",
        "chorale_target_voices",
        "chorale_visible_voices",
        "chorale_label_mode",
        "chorale_show_chord_labels",
        "chorale_show_notation",
        "chorale_transpose",
        "chorale_tempo",
        "chorale_wait_mode",
        "chorale_onset_window_ms",
        "chorale_release_tolerance_pct",
        "chorale_octave_flexible",
        "chorale_chord_member_min",
        "chorale_excerpt_start",
        "chorale_excerpt_end",
    ]

    CHORALE_SUPPRESSED_FIELDS = [
        "rhythm",
        "visibility_pattern",
        "time_signature",
        "semibreves_per_line",
    ]

    def _detect_chorale(self):
        data = {}
        if self.instance and getattr(self.instance, "data", None):
            data = self.instance.data
        initial_type = None
        if hasattr(self, "initial"):
            initial_type = self.initial.get("type")
        form_type = data.get("type") or initial_type
        bound_data = getattr(self, "data", None)
        if not form_type and bound_data and "type" in bound_data:
            form_type = bound_data.get("type")
        return form_type == self.TYPE_CHORALE

    def _configure_type_field(self):
        if "type" not in self.fields:
            return
        if self._is_chorale:
            choices = list(self.fields["type"].choices)
            if (self.TYPE_CHORALE, "Chorale score") not in choices:
                choices.append((self.TYPE_CHORALE, "Chorale score"))
            self.fields["type"].choices = choices
            self.fields["type"].initial = self.TYPE_CHORALE
            self.fields["type"].widget = forms.HiddenInput()
        elif self._is_chorale_identification:
            choices = list(self.fields["type"].choices)
            if (self.TYPE_CHORALE_IDENTIFICATION, "Chorale identification") not in choices:
                choices.append((self.TYPE_CHORALE_IDENTIFICATION, "Chorale identification"))
            self.fields["type"].choices = choices
            self.fields["type"].initial = self.TYPE_CHORALE_IDENTIFICATION
            self.fields["type"].widget = forms.HiddenInput()
        elif self._is_identification:
            choices = list(self.fields["type"].choices)
            if (self.TYPE_IDENTIFICATION, "Identification") not in choices:
                choices.append((self.TYPE_IDENTIFICATION, "Identification"))
            self.fields["type"].choices = choices
            self.fields["type"].initial = self.TYPE_IDENTIFICATION
            self.fields["type"].widget = forms.HiddenInput()
        else:
            filtered = [
                c for c in self.fields["type"].choices
                if c[0] not in (self.TYPE_CHORALE, self.TYPE_IDENTIFICATION, self.TYPE_CHORALE_IDENTIFICATION)
            ]
            self.fields["type"].choices = tuple(filtered)

    def _configure_chorale_fields(self):
        if not self._is_chorale:
            for field in self.CHORALE_ONLY_FIELDS:
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()
            return

        # Hide legacy-only inputs
        for field in self.CHORALE_SUPPRESSED_FIELDS:
            if field in self.fields:
                self.fields[field].widget = forms.HiddenInput()

        # Staff distribution is forced to chorale
        if "staff_distribution" in self.fields:
            self.fields["staff_distribution"].initial = self.DISTRIBUTION_CHORALE
            self.fields["staff_distribution"].widget = forms.HiddenInput()

        score = {}
        if self.instance and getattr(self.instance, "data", None):
            score = self.instance.data.get("score", {})
        self._chorale_voice_choices = self._build_voice_choices(score)
        self._init_chorale_initials(score)

    def _build_voice_choices(self, score):
        measures = (score or {}).get("measures", [])
        if not measures:
            return []
        staff_map = measures[0].get("staves", {})
        choices = []
        friendly_names = {
            ("treble", 0): "Soprano",
            ("treble", 1): "Alto",
            ("bass", 0): "Tenor",
            ("bass", 1): "Bass",
        }
        for staff_key, staff in staff_map.items():
            voices = staff.get("voices", []) if isinstance(staff, dict) else []
            for idx, _voice in enumerate(voices):
                token = f"{staff_key}:{idx}"
                label = friendly_names.get((staff_key, idx))
                if not label:
                    label = f"{staff_key.title()} voice {idx + 1}"
                choices.append((token, label))
        if "chorale_target_voices" in self.fields:
            self.fields["chorale_target_voices"].choices = choices
        if "chorale_visible_voices" in self.fields:
            self.fields["chorale_visible_voices"].choices = choices
        return choices

    def _init_chorale_initials(self, score):
        data = self.instance.data if self.instance and getattr(self.instance, "data", None) else {}
        display = data.get("display", {}) or {}
        grading = data.get("grading", {}) or {}
        excerpt = data.get("excerpt", {}) or {}

        analysis_mode = (data.get("analysis", {}) or {}).get("mode", {}) or {}
        label_mode = display.get("figureStyle") or "none"
        if label_mode.startswith("figures") and not display.get("showFigures"):
            label_mode = "none"
        if label_mode == "none":
            if display.get("showRomansExp"):
                label_mode = "romans_exp"
            elif display.get("showRomans"):
                label_mode = "romans"
            elif display.get("showFigures"):
                label_mode = (
                    "figures_abbrev"
                    if analysis_mode.get("abbreviate_thoroughbass")
                    else "figures"
                )
            elif display.get("showNoteNames"):
                label_mode = "note_names"

        defaults = {
            "chorale_mode": data.get("mode") or "play-all-voices",
            "chorale_label_mode": label_mode,
            "chorale_show_chord_labels": display.get("showChordLabels", False),
            "chorale_tempo": display.get("tempo", 60),
            "chorale_wait_mode": display.get("waitMode", False),
            "chorale_show_notation": display.get("showNotation", True),
            "chorale_onset_window_ms": grading.get("onsetWindowMs", 150),
            "chorale_release_tolerance_pct": grading.get("releaseTolerancePct", 40),
            "chorale_octave_flexible": grading.get("octaveFlexible", False),
            "chorale_chord_member_min": grading.get("chordMemberMin", None),
            "chorale_excerpt_start": excerpt.get("startMeasure"),
            "chorale_excerpt_end": excerpt.get("endMeasure"),
        }
        for field, value in defaults.items():
            if field in self.fields:
                self.fields[field].initial = value

        target_tokens = self._voice_tokens_from_mapping(data.get("targetVoices"))
        visible_tokens = self._voice_tokens_from_mapping(display.get("visibleVoices"))

        if "chorale_target_voices" in self.fields:
            if not target_tokens and self._chorale_voice_choices:
                target_tokens = [choice[0] for choice in self._chorale_voice_choices]
            self.fields["chorale_target_voices"].initial = target_tokens
        if "chorale_visible_voices" in self.fields:
            if not visible_tokens and self._chorale_voice_choices:
                visible_tokens = [choice[0] for choice in self._chorale_voice_choices]
            self.fields["chorale_visible_voices"].initial = visible_tokens

        help_map = {
            "chorale_mode": "Choose the assignment style (all voices, melody only, etc.).",
            "chorale_target_voices": "Only these voices must be performed correctly to pass.",
            "chorale_visible_voices": "Toggles which staves/voices are drawn on the score.",
            "chorale_label_mode": "Select exactly one overlay: note names, figured bass, Roman numerals, or hide labels.",
            "chorale_show_chord_labels": "Adds lead-sheet chord symbols (F, C/E, etc.) alongside the selected overlay.",
            "chorale_transpose": "Shift the printed score and required pitches by the given semitones.",
            "chorale_tempo": "Viewport tempo in BPM (purely informational for now).",
            "chorale_wait_mode": "When enabled, the viewport waits at the current onset until notes are correct.",
            "chorale_onset_window_ms": "How many milliseconds early/late a played note can be and still count as on time.",
            "chorale_release_tolerance_pct": "What fraction of the notated duration the student must hold before releasing.",
            "chorale_octave_flexible": "Allow correct notes in any octave (useful for limited keyboards).",
            "chorale_chord_member_min": "Require at least this many chord members at each onset (use 0/blank to require all).",
            "chorale_show_notation": "Whether to draw the musical staff notation.",
            "chorale_excerpt_start": "Optional starting measure index for the viewport.",
            "chorale_excerpt_end": "Optional ending measure index (exclusive).",
        }
        for field, text in help_map.items():
            self._set_help_icon(field, text)

    def _voice_tokens_from_mapping(self, mapping):
        if not mapping or mapping == "all":
            return []
        tokens = []
        if isinstance(mapping, dict):
            for staff, voices in mapping.items():
                for idx in voices:
                    tokens.append(f"{staff}:{idx}")
        elif isinstance(mapping, list):
            # already encoded tokens
            tokens = [str(token) for token in mapping]
        return tokens

    def _store_chorale_settings(self, instance):
        data = instance.data
        display = data.get("display", {}) or {}
        grading = data.get("grading", {}) or {}

        data["type"] = self.TYPE_CHORALE
        data["staffDistribution"] = self.DISTRIBUTION_CHORALE
        data["mode"] = (
            self.cleaned_data.get("chorale_mode") or data.get("mode") or "play-all-voices"
        )

        target_tokens = self.cleaned_data.get("chorale_target_voices") or []
        data["targetVoices"] = self._serialize_voice_selection(
            target_tokens, allow_all=True
        )

        visible_tokens = self.cleaned_data.get("chorale_visible_voices") or []
        serialized_visible = self._serialize_voice_selection(
            visible_tokens, allow_all=True
        )
        if serialized_visible == "all":
            display.pop("visibleVoices", None)
        else:
            display["visibleVoices"] = serialized_visible

        raw_label_mode = self.cleaned_data.get("chorale_label_mode") or "none"
        label_mode = raw_label_mode
        display["figureStyle"] = (
            raw_label_mode if raw_label_mode.startswith("figures") else None
        )
        if display["figureStyle"] is None and "figureStyle" in display:
            display.pop("figureStyle", None)
        display["showFigures"] = raw_label_mode in ("figures", "figures_abbrev")
        display["showRomans"] = label_mode == "romans"
        display["showRomansExp"] = label_mode == "romans_exp"
        display["showNoteNames"] = label_mode == "note_names"
        display["showChordLabels"] = self.cleaned_data.get(
            "chorale_show_chord_labels", False
        )
        transpose = self.cleaned_data.get("chorale_transpose")
        display["transpose"] = transpose if transpose is not None else display.get("transpose", 0)
        tempo = self.cleaned_data.get("chorale_tempo")
        display["tempo"] = tempo if tempo is not None else display.get("tempo", 60)
        display["waitMode"] = self.cleaned_data.get("chorale_wait_mode", False)
        display["showNotation"] = self.cleaned_data.get("chorale_show_notation", True)
        display["analysisRenderer"] = (
            "notater"
            if display["showFigures"]
            or display["showRomans"]
            or display["showRomansExp"]
            or display["showChordLabels"]
            or display["showNoteNames"]
            else "none"
        )

        onset_window = self.cleaned_data.get("chorale_onset_window_ms")
        if onset_window is not None:
            grading["onsetWindowMs"] = onset_window
        release_tol = self.cleaned_data.get("chorale_release_tolerance_pct")
        if release_tol is not None:
            grading["releaseTolerancePct"] = release_tol
        grading["octaveFlexible"] = self.cleaned_data.get("chorale_octave_flexible", False)
        grading["octaveIndependent"] = grading["octaveFlexible"]
        chord_min = self.cleaned_data.get("chorale_chord_member_min")
        if chord_min:
            grading["chordMemberMin"] = chord_min
        elif "chordMemberMin" in grading:
            grading.pop("chordMemberMin")

        data["display"] = display
        data["grading"] = grading

        start_measure = self.cleaned_data.get("chorale_excerpt_start")
        end_measure = self.cleaned_data.get("chorale_excerpt_end")
        if start_measure is not None or end_measure is not None:
            data["excerpt"] = data.get("excerpt", {}) or {}
            if start_measure is not None:
                data["excerpt"]["startMeasure"] = start_measure
            if end_measure is not None:
                data["excerpt"]["endMeasure"] = end_measure

        self._apply_chorale_analysis_settings(
            data,
            raw_label_mode,
            display["showChordLabels"],
            display["showNoteNames"],
        )

    def _apply_chorale_analysis_settings(self, data, label_mode, show_chords, show_note_names=False):
        analysis = data.get("analysis", {}) or {}
        mode = {key: False for key in CHORALE_ANALYSIS_KEYS}
        mode["thoroughbass"] = label_mode in ("figures", "figures_abbrev")
        mode["abbreviate_thoroughbass"] = label_mode == "figures_abbrev"
        mode["roman_numerals"] = label_mode == "romans"
        mode["roman_numerals_exp"] = label_mode == "romans_exp"
        mode["chord_labels"] = bool(show_chords)
        mode["note_names"] = bool(show_note_names)

        analysis["mode"] = mode
        analysis["enabled"] = any(mode.values())
        data["analysis"] = analysis

    def _serialize_voice_selection(self, tokens, allow_all=False):
        if not tokens:
            return "all" if allow_all else {}
        if allow_all and self._chorale_voice_choices:
            all_tokens = {choice[0] for choice in self._chorale_voice_choices}
            if set(tokens) == all_tokens:
                return "all"
        mapping = {}
        for token in tokens:
            if ":" not in token:
                continue
            staff, idx = token.split(":", 1)
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                continue
            mapping.setdefault(staff, []).append(idx)
        return mapping or ("all" if allow_all else {})

    def _set_help_icon(self, field_name, description):
        if not self._is_chorale or field_name not in self.fields or not description:
            return
        text = conditional_escape(description)
        self.fields[field_name].help_text = format_html(
            '<span class="hl-help-icon" tabindex="0" role="img" aria-label="{0}" '
            'data-tooltip="{0}"></span>',
            text,
        )

    # --------------------
    # Identification helpers
    # --------------------

    IDENT_ONLY_FIELDS = ["ident_mode"]

    INTERVAL_ANALYSIS_TYPES = ("interval_generic", "interval_specific")

    INTERVAL_ONLY_FIELDS = ["compound_intervals"]

    IDENT_SUPPRESSED_FIELDS = [
        "rhythm",
        "visibility_pattern",
        "time_signature",
        "semibreves_per_line",
        "staff_distribution",
    ]

    def _detect_identification(self):
        data = {}
        if self.instance and getattr(self.instance, "data", None):
            data = self.instance.data
        form_type = data.get("type")
        bound_data = getattr(self, "data", None)
        if not form_type and bound_data and "type" in bound_data:
            form_type = bound_data.get("type")
        return form_type in (self.TYPE_IDENTIFICATION, self.TYPE_CHORALE_IDENTIFICATION)

    def _detect_chorale_identification(self):
        data = {}
        if self.instance and getattr(self.instance, "data", None):
            data = self.instance.data
        form_type = data.get("type")
        bound_data = getattr(self, "data", None)
        if not form_type and bound_data and "type" in bound_data:
            form_type = bound_data.get("type")
        return form_type == self.TYPE_CHORALE_IDENTIFICATION

    def _configure_identification_fields(self):
        if not self._is_identification:
            for field in self.IDENT_ONLY_FIELDS:
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()
            return

        # Hide fields that don't apply to identification
        for field in self.IDENT_SUPPRESSED_FIELDS:
            if field in self.fields:
                self.fields[field].widget = forms.HiddenInput()

        # Populate initial values from existing data
        if self.instance and getattr(self.instance, "data", None):
            ident_mode = self.instance.data.get("identMode", "submit")
            if "ident_mode" in self.fields:
                self.fields["ident_mode"].initial = ident_mode

    def _store_identification_settings(self, instance):
        ident_mode = self.cleaned_data.get("ident_mode") or "submit"
        instance.data["identMode"] = ident_mode

    def _detect_interval(self):
        data = {}
        if self.instance and getattr(self.instance, "data", None):
            data = self.instance.data
        return data.get("analysisType") in self.INTERVAL_ANALYSIS_TYPES

    def _configure_interval_fields(self):
        if not self._detect_interval():
            for field in self.INTERVAL_ONLY_FIELDS:
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()
            return
        if self.instance and getattr(self.instance, "data", None):
            compound = self.instance.data.get("compoundIntervals", False)
            if "compound_intervals" in self.fields:
                self.fields["compound_intervals"].initial = compound

    def _store_interval_settings(self, instance):
        instance.data["compoundIntervals"] = bool(self.cleaned_data.get("compound_intervals", False))



class PlaylistForm(forms.ModelForm):
    # EXPANSIVE_FIELD = "exercises"
    # EXPANSIVE_FIELD_MODEL = Exercise
    # EXPANSIVE_FIELD_INITIAL = "E"

    transposition_type = forms.ChoiceField(
        choices=Playlist.TRANSPOSE_TYPE_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        label="Transposition method",
        help_text="",
    )

    tags = forms.MultipleChoiceField(
        choices=CONTENT_TAGS,
        widget=CollapsibleCheckboxSelectMultiple,
        required=False,
        label="Tags",
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
        "is_dynamic",
        "is_adaptive",
        "feedback_mode",
        "tags",
        "min_complexity",
        "max_complexity",
        "is_auto",
        "transposition_type",
        "transpose_requests",
        "exercises",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["tags"].initial = list(self.instance.tags or [])


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        exclude = ("performance_dict",)
        widgets = {
            "id": forms.TextInput(attrs={"readonly": "readonly"}),
            # "visible_to":forms.CheckboxSelectMultiple()
        }


class PerformanceDataForm(forms.ModelForm):
    class Meta:
        model = PerformanceData
        exclude = []
        widgets = {
            "data": PrettyJSONWidget(),
        }
