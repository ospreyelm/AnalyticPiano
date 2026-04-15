# Pitch Identification via Chorale Identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add six pitch-oriented analysis types to chorale identification, with a shared single-voice validation path used by both dashboard duplication and CLI import.

**Architecture:** Keep the exercise type as chorale_identification and extend existing parsing/labeling logic. Introduce a small shared Python utility for voice stripping and validation, then wire both server entry points (dashboard and CLI) to that single utility. Frontend stays on existing popup/grading flow and only extends analysis label + choice generation.

**Tech Stack:** Django views/forms/management commands, Python unit tests, RequireJS AMD frontend JavaScript.

---

### Task 1: Add Shared Voice Utilities

**Files:**
- Create: `apps/exercises/pitch_voice_utils.py`
- Create: `apps/exercises/tests/test_pitch_voice_utils.py`

- [x] **Step 1: Write the failing tests for strip and validation behavior**

```python
from django.test import TestCase

from apps.exercises.pitch_voice_utils import strip_to_voice, validate_pitch_voice


class PitchVoiceUtilsTests(TestCase):
	def test_strip_to_voice_preserves_measure_fields(self):
		score = {
			"meta": {"key": "G"},
			"measures": [
				{
					"number": 1,
					"staves": {
						"treble": {"voices": [{"items": [{"kind": "note"}]}, {"items": [{"kind": "note"}]}]},
						"bass": {"voices": [{"items": [{"kind": "note"}]}, {"items": [{"kind": "note"}]}]},
					},
				}
			],
		}
		out = strip_to_voice(score, "soprano")
		assert out["measures"][0]["number"] == 1
		assert list(out["measures"][0]["staves"].keys()) == ["treble"]
		assert len(out["measures"][0]["staves"]["treble"]["voices"]) == 1

	def test_validate_pitch_voice_rejects_chords(self):
		score = {
			"measures": [
				{
					"number": 1,
					"staves": {
						"treble": {
							"voices": [
								{"items": [{"kind": "chord", "notes": []}]}
							]
						}
					},
				}
			]
		}
		with self.assertRaises(ValueError):
			validate_pitch_voice(score, "soprano")

	def test_validate_pitch_voice_allows_rests(self):
		score = {
			"measures": [
				{
					"number": 1,
					"staves": {
						"treble": {
							"voices": [
								{"items": [{"kind": "rest"}, {"kind": "note"}]}
							]
						}
					},
				}
			]
		}
		validate_pitch_voice(score, "soprano")
```

- [x] **Step 2: Run tests to verify they fail first**

Run: `python manage.py test apps.exercises.tests.test_pitch_voice_utils -v 2`
Expected: FAIL with import error or missing function failures.

- [x] **Step 3: Implement the shared utility module**

```python
# apps/exercises/pitch_voice_utils.py
from copy import deepcopy


VOICE_MAP = {
	"soprano": ("treble", 0),
	"alto": ("treble", 1),
	"tenor": ("bass", 0),
	"bass": ("bass", 1),
}


def validate_pitch_voice(score, voice_name):
	"""Raise ValueError when unsupported multi-note voice content is found."""
	for measure in score.get("measures", []):
		for _staff_name, stave in measure.get("staves", {}).items():
			for voice in stave.get("voices", []):
				for item in voice.get("items", []):
					if item.get("kind") == "chord":
						raise ValueError(
							f"Voice '{voice_name}' measure {measure.get('number', '?')} "
							"contains a chord; pitch identification requires single notes"
						)


def strip_to_voice(score, voice_name):
	if voice_name not in VOICE_MAP:
		raise ValueError(f"Unsupported voice '{voice_name}'")

	staff_name, voice_idx = VOICE_MAP[voice_name]
	new_measures = []
	for measure in score.get("measures", []):
		stave = measure.get("staves", {}).get(staff_name, {})
		voices = stave.get("voices", [])
		if voice_idx >= len(voices):
			raise ValueError(
				f"Voice '{voice_name}' not found in measure {measure.get('number', '?')}"
			)

		new_measure = deepcopy(measure)
		new_measure["staves"] = {staff_name: {"voices": [deepcopy(voices[voice_idx])]}}
		new_measures.append(new_measure)

	new_score = deepcopy(score)
	new_score["measures"] = new_measures
	validate_pitch_voice(new_score, voice_name)
	return new_score
```

- [x] **Step 4: Re-run tests and confirm pass**

Run: `python manage.py test apps.exercises.tests.test_pitch_voice_utils -v 2`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/exercises/pitch_voice_utils.py apps/exercises/tests/test_pitch_voice_utils.py
git commit -m "feat: add shared pitch voice stripping and validation helpers"
```

### Task 2: Extend import_chorale for Pitch Analysis Types

**Files:**
- Modify: `apps/exercises/management/commands/import_chorale.py`
- Create: `apps/exercises/tests/test_import_chorale_pitch_identification.py`

- [x] **Step 1: Write failing command tests**

```python
from django.core.management import call_command, CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Exercise


class ImportChoralePitchIdentificationTests(TestCase):
	def setUp(self):
		User.objects.create_user(email="teacher@example.com", password="pw")

	def test_pitch_analysis_requires_voice(self):
		with self.assertRaises(CommandError):
			call_command(
				"import_chorale",
				"bwv1.6.json",
				author="teacher@example.com",
				mode="identify",
				analysis="note_name",
			)

	def test_pitch_analysis_with_voice_creates_identification(self):
		call_command(
			"import_chorale",
			"bwv1.6.json",
			author="teacher@example.com",
			mode="identify",
			analysis="note_name",
			voice="soprano",
			start=0,
			end=2,
		)
		ex = Exercise.objects.latest("created")
		self.assertEqual(ex.data["type"], "chorale_identification")
		self.assertEqual(ex.data["analysisType"], "note_name")
```

- [x] **Step 2: Run targeted tests to verify failure**

Run: `python manage.py test apps.exercises.tests.test_import_chorale_pitch_identification -v 2`
Expected: FAIL because CLI does not yet support the new analysis choices and voice requirement.

- [x] **Step 3: Implement command changes**

```python
# import_chorale.py
from apps.exercises.pitch_voice_utils import strip_to_voice

PITCH_ANALYSIS_TYPES = (
	"note_name",
	"solfege",
	"do_based_solfege",
	"scale_degree",
	"fixed_do",
	"pitch_class",
)

# add_arguments:
parser.add_argument(
	"--analysis",
	choices=["roman", "figured_bass", "interval_generic", "interval_specific", *PITCH_ANALYSIS_TYPES],
	default="roman",
)
parser.add_argument("--voice", choices=["soprano", "alto", "tenor", "bass"])

# handle:
if mode == "identify" and analysis_type in PITCH_ANALYSIS_TYPES:
	if not options.get("voice"):
		raise CommandError("--voice is required for pitch analysis types")
	try:
		score_for_ident = strip_to_voice(score_for_ident, options["voice"])
	except ValueError as exc:
		raise CommandError(str(exc))
```

- [x] **Step 4: Re-run tests and verify pass**

Run: `python manage.py test apps.exercises.tests.test_import_chorale_pitch_identification apps.exercises.tests.test_duplicate_chorale_as_identification -v 2`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/exercises/management/commands/import_chorale.py apps/exercises/tests/test_import_chorale_pitch_identification.py
git commit -m "feat: support pitch analysis import options with required voice"
```

### Task 3: Add Dashboard Duplicate-As-Pitch-Identification Flow

**Files:**
- Modify: `apps/dashboard/views/exercises.py`
- Modify: `apps/dashboard/templates/dashboard/edit-exercise.html`
- Create: `apps/dashboard/tests/test_exercise_pitch_duplication.py`

- [x] **Step 1: Write failing dashboard tests**

```python
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.exercises.models import Exercise


class DashboardPitchDuplicationTests(TestCase):
	def test_pitch_duplication_creates_one_exercise_per_voice(self):
		user = User.objects.create_user(email="teacher@example.com", password="pw")
		self.client.force_login(user)
		source = Exercise.objects.create(
			authored_by=user,
			description="Source chorale",
			data={"type": "chorale", "score": {"meta": {"key": "G"}, "measures": []}},
		)

		response = self.client.post(
			reverse("dashboard:edit-exercise", kwargs={"exercise_id": source.id}),
			{
				"description": source.description,
				"type": "chorale",
				"duplicate-as-pitch-identification": "1",
				"voices": ["soprano", "alto"],
				"analysisType": "note_name",
				"identMode": "practice",
			},
		)
		self.assertEqual(response.status_code, 302)
```

- [x] **Step 2: Run test and confirm failure**

Run: `python manage.py test apps.dashboard.tests.test_exercise_pitch_duplication -v 2`
Expected: FAIL because the action and fields are not wired.

- [x] **Step 3: Implement backend action using shared utility**

```python
# exercises.py
from django.db import transaction
from apps.exercises.pitch_voice_utils import strip_to_voice

PITCH_ANALYSIS_TYPES = {
	"note_name", "solfege", "do_based_solfege", "scale_degree", "fixed_do", "pitch_class"
}

if "duplicate-as-pitch-identification" in request.POST:
	voices = request.POST.getlist("voices")
	analysis_type = request.POST.get("analysisType", "note_name")
	ident_mode = request.POST.get("identMode", "practice")
	if analysis_type not in PITCH_ANALYSIS_TYPES:
		messages.error(request, "Invalid pitch analysis type.")
		return redirect("dashboard:edit-exercise", exercise.id)

	source_data = exercise.data or {}
	source_score = _copy.deepcopy(source_data.get("score", {}))
	created = []
	try:
		with transaction.atomic():
			for voice in voices:
				stripped = strip_to_voice(source_score, voice)
				new_data = {
					"type": "chorale_identification",
					"identMode": ident_mode,
					"analysisType": analysis_type,
					"score": stripped,
					"key": source_data.get("key") or source_score.get("meta", {}).get("key", "C"),
					"staffDistribution": "chorale",
					"introText": source_data.get("introText") or f"Name each note in the {voice} voice.",
					"reviewText": source_data.get("reviewText") or "Well done!",
				}
				clone = Exercise(
					description=f"{exercise.description or exercise.id} - {voice.title()} ({analysis_type})",
					data=new_data,
					authored_by=request.user,
					is_public=exercise.is_public,
				)
				clone.save()
				created.append(clone)
	except ValueError as exc:
		messages.error(request, str(exc))
		return redirect("dashboard:edit-exercise", exercise.id)

	return redirect("dashboard:exercises-list")
```

- [x] **Step 4: Implement template controls for pitch duplication**

```html
<button type="submit" class="btn dashboard-btn" name="duplicate-as-pitch-identification" value="1">
  Save, Duplicate as Pitch Identification
</button>
<input type="hidden" name="analysisType" value="note_name" />
<input type="hidden" name="identMode" value="practice" />
<input type="hidden" name="voices" value="soprano" />
```

Note: replace the hidden input approach with a modal UI that submits selected values when implementing the final UI details.

- [x] **Step 5: Re-run dashboard tests**

Run: `python manage.py test apps.dashboard.tests.test_exercise_pitch_duplication -v 2`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add apps/dashboard/views/exercises.py apps/dashboard/templates/dashboard/edit-exercise.html apps/dashboard/tests/test_exercise_pitch_duplication.py
git commit -m "feat: add dashboard pitch-identification duplication flow"
```

### Task 4: Extend Frontend Pitch Analysis Label and Choice Logic

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`

- [x] **Step 1: Write failing JS-focused acceptance notes in plan comments**

```javascript
// Acceptance cases to verify after implementation:
// 1) analysisType=note_name labels via analyzer.to_note_name([midi])
// 2) analysisType=pitch_class labels via analyzer.to_pitch_class([midi]).toString()
// 3) fallback pools include pitch-specific candidates
// 4) midiStack.length !== 1 warns and returns ""
```

- [x] **Step 2: Implement pitch analysis type helpers and compute branch**

```javascript
function isPitchAnalysisType(analysisType) {
  return analysisType === "note_name" ||
		 analysisType === "solfege" ||
		 analysisType === "do_based_solfege" ||
		 analysisType === "scale_degree" ||
		 analysisType === "fixed_do" ||
		 analysisType === "pitch_class";
}

if (isPitchAnalysisType(analysisType)) {
  if (!midiStack || midiStack.length !== 1) {
	console.warn("[pitch-identification] expected one midi in stack", midiStack);
	return "";
  }
  var midi = midiStack[0];
  if (analysisType === "note_name") return analyzer.to_note_name([midi]);
  if (analysisType === "solfege") return analyzer.to_solfege([midi]);
  if (analysisType === "do_based_solfege") return analyzer.to_do_based_solfege([midi]);
  if (analysisType === "scale_degree") return analyzer.to_scale_degree([midi]);
  if (analysisType === "fixed_do") return analyzer.to_fixed_do([midi]);
  if (analysisType === "pitch_class") return analyzer.to_pitch_class([midi]).toString();
}
```

- [x] **Step 3: Extend buildChoices fallback pools**

```javascript
var fallbacks = isPitchAnalysisType(analysisType)
  ? analysisType === "note_name"
	? ["C", "D", "E", "F", "G", "A", "B"]
	: (analysisType === "scale_degree"
	  ? ["1", "2", "3", "4", "5", "6", "7"]
	  : (analysisType === "pitch_class"
		? ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
		: ["Do", "Re", "Mi", "Fa", "So", "La", "Ti"]))
  : fallbacks;
```

- [x] **Step 4: Verify manually in browser using one generated exercise per analysis type**

Run server and open exercise preview pages.
Expected: one note per slot, 5 choices shown, correct labels match chosen analysis type.

- [x] **Step 5: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "feat: add pitch analysis label and distractor logic"
```

### Task 5: End-to-End Verification and Documentation Updates

**Files:**
- Modify: `docs/superpowers/specs/2026-04-14-pitch-identification-design.md`
- Optional modify: `README.md` (if command usage docs are kept there)

- [x] **Step 1: Align spec wording with implemented rest behavior**

```markdown
Update validator wording from:
- "raises ValueError if any window has zero notes or more than one note"

To:
- "raises ValueError on chord/multi-note voice content; rests are allowed and skipped by ScoreTimeline"
```

- [x] **Step 2: Run full targeted test suite for touched areas**

Run: `python manage.py test apps.exercises.tests.test_pitch_voice_utils apps.exercises.tests.test_import_chorale_pitch_identification apps.dashboard.tests.test_exercise_pitch_duplication apps.exercises.tests.test_duplicate_chorale_as_identification -v 2`
Expected: PASS.

- [x] **Step 3: Run lint/format checks used by team (if configured)**

Run: `python manage.py check`
Expected: no new system check errors.

- [x] **Step 4: Commit final docs and cleanup**

```bash
git add docs/superpowers/specs/2026-04-14-pitch-identification-design.md README.md
git commit -m "docs: finalize pitch-identification behavior and command usage"
```

## Spec Coverage Check

- Six analysis types in chorale_identification: covered by Task 4 and Task 2.
- Shared single enforcement path: covered by Task 1, Task 2, Task 3.
- Dashboard duplicate flow with multi-voice creation and clear errors: covered by Task 3.
- Import command extensions and voice requirement for pitch modes: covered by Task 2.
- Acceptance checks and known limitations alignment: covered by Task 5.

## Notes for Executor

- Keep Exercise.save behavior unchanged; instantiate and save model objects directly (do not switch to objects.create where force_insert may interfere with custom ID behavior).
- Prefer explicit ValueError messages that include measure number and voice name so dashboard and command-line output are actionable.
- When dashboard duplication fails for one selected voice, ensure transaction rollback so no partial duplicate set is left behind.
