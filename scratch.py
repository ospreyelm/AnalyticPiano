import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "harmony.settings.local")
django.setup()

from apps.exercises.models import Exercise
import json

json_data = """{
"key": "iD_",
"clef": "bass",
"mode": "analysis_match",
"type": "umto_chorale",
"meter": "4/4",
"score": {
"meta": {
"key": "iD_",
"clef": "bass",
"time": "4/4",
"staffDistribution": "bass"
},
"umto": {
"voices": {
"A": [ ],
"B": [
{
"dots": 0,
"kind": "note",
"pitch": {
"midi": 43,
"step": "G",
"alter": 0,
"octave": 2
},
"duration": 0.5,
"is_target": true,
"is_tied_stop": false,
"duration_type": "8",
"is_tied_start": false
},
{
"dots": 0,
"kind": "note",
"pitch": {
"midi": 45,
"step": "A",
"alter": 0,
"octave": 2
},
"duration": 0.5,
"is_target": true,
"is_tied_stop": false,
"duration_type": "8",
"is_tied_start": false
},
{
"dots": 0,
"kind": "note",
"pitch": {
"midi": 46,
"step": "B",
"alter": -1,
"octave": 2
},
"duration": 1,
"is_target": true,
"is_tied_stop": false,
"duration_type": "q",
"is_tied_start": false
},
{
"dots": 0,
"kind": "note",
"pitch": {
"midi": 45,
"step": "A",
"alter": 0,
"octave": 2
},
"duration": 0.5,
"is_target": true,
"is_tied_stop": false,
"duration_type": "8",
"is_tied_start": false
},
{
"dots": 0,
"kind": "note",
"pitch": {
"midi": 46,
"step": "B",
"alter": -1,
"octave": 2
},
"duration": 0.5,
"is_target": true,
"is_tied_stop": false,
"duration_type": "8",
"is_tied_start": false
},
{
"dots": 0,
"kind": "note",
"pitch": {
"midi": 48,
"step": "C",
"alter": 0,
"octave": 3
},
"duration": 1,
"is_target": true,
"is_tied_stop": false,
"duration_type": "q",
"is_tied_start": false
},
{
"dots": 1,
"kind": "note",
"pitch": {
"midi": 41,
"step": "F",
"alter": 0,
"octave": 2
},
"duration": 3,
"is_target": true,
"is_tied_stop": false,
"duration_type": "h",
"is_tied_start": false
},
{
"dots": 0,
"kind": "rest",
"pitch": null,
"duration": 1,
"is_target": true,
"is_tied_stop": false,
"duration_type": "q",
"is_tied_start": false
}
],
"S": [ ],
"T": [ ]
},
"grading": [
{
"offset": 0,
"target_midi_pitches": [
43
],
"rhythmic_flexibility": false
},
{
"offset": 0.5,
"target_midi_pitches": [
45
],
"rhythmic_flexibility": false
},
{
"offset": 1,
"target_midi_pitches": [
46
],
"rhythmic_flexibility": false
},
{
"offset": 2,
"target_midi_pitches": [
45
],
"rhythmic_flexibility": false
},
{
"offset": 2.5,
"target_midi_pitches": [
46
],
"rhythmic_flexibility": false
},
{
"offset": 3,
"target_midi_pitches": [
48
],
"rhythmic_flexibility": false
},
{
"offset": 4,
"target_midi_pitches": [
41
],
"rhythmic_flexibility": false
}
],
"analysis": [
{
"offset": 0,
"visual": null,
"content": {
"pop_symbol": null,
"figured_bass": null,
"roman_numeral": null,
"functional_label": null
},
"unit_tags": [
1
]
},
{
"offset": 0.5,
"visual": null,
"content": {
"pop_symbol": null,
"figured_bass": null,
"roman_numeral": null,
"functional_label": null
},
"unit_tags": [
1
]
},
{
"offset": 1,
"visual": null,
"content": {
"pop_symbol": null,
"figured_bass": null,
"roman_numeral": null,
"functional_label": null
},
"unit_tags": [
1
]
},
{
"offset": 2,
"visual": null,
"content": {
"pop_symbol": null,
"figured_bass": null,
"roman_numeral": null,
"functional_label": null
},
"unit_tags": [
1
]
},
{
"offset": 2.5,
"visual": null,
"content": {
"pop_symbol": null,
"figured_bass": null,
"roman_numeral": null,
"functional_label": null
},
"unit_tags": [
1
]
},
{
"offset": 3,
"visual": null,
"content": {
"pop_symbol": null,
"figured_bass": null,
"roman_numeral": null,
"functional_label": null
},
"unit_tags": [
1
]
},
{
"offset": 4,
"visual": null,
"content": {
"pop_symbol": null,
"figured_bass": null,
"roman_numeral": null,
"functional_label": null
},
"unit_tags": [
1
]
}
],
"metadata": {
"key": "iD_",
"clef": "bass",
"mode": "analysis_match",
"meter": "4/4",
"source": "Name the notes: BWV96.6, measures 11-12, Bass voice.",
"is_umto": true,
"exercise_id": "EA96YW",
"complexity_score": 1
}
},
"measures": [
{
"staves": {
"bass": {
"clef": "bass",
"voices": [
{
"items": [
{
"kind": "note",
"pitch": {
"step": "G",
"alter": 0,
"octave": 2
},
"duration": {
"dots": 0,
"type": "8"
}
},
{
"kind": "note",
"pitch": {
"step": "A",
"alter": 0,
"octave": 2
},
"duration": {
"dots": 0,
"type": "8"
}
},
{
"kind": "note",
"pitch": {
"step": "B",
"alter": -1,
"octave": 2
},
"duration": {
"dots": 0,
"type": "q"
}
},
{
"kind": "note",
"pitch": {
"step": "A",
"alter": 0,
"octave": 2
},
"duration": {
"dots": 0,
"type": "8"
}
},
{
"kind": "note",
"pitch": {
"step": "B",
"alter": -1,
"octave": 2
},
"duration": {
"dots": 0,
"type": "8"
}
},
{
"kind": "note",
"pitch": {
"step": "C",
"alter": 0,
"octave": 3
},
"duration": {
"dots": 0,
"type": "q"
}
},
{
"kind": "note",
"pitch": {
"step": "F",
"alter": 0,
"octave": 2
},
"duration": {
"dots": 1,
"type": "h"
}
},
{
"kind": "rest",
"duration": {
"dots": 0,
"type": "q"
}
}
],
"direction": "auto"
}
]
},
"treble": {
"clef": "treble",
"voices": [ ]
}
}
}
]
},
"isUMTO": true,
"display": {
"showNotation": false,
"showNoteNames": true
},
"grading": [
{
"offset": 0,
"target_midi_pitches": [
43
],
"rhythmic_flexibility": false
},
{
"offset": 0.5,
"target_midi_pitches": [
45
],
"rhythmic_flexibility": false
},
{
"offset": 1,
"target_midi_pitches": [
46
],
"rhythmic_flexibility": false
},
{
"offset": 2,
"target_midi_pitches": [
45
],
"rhythmic_flexibility": false
},
{
"offset": 2.5,
"target_midi_pitches": [
46
],
"rhythmic_flexibility": false
},
{
"offset": 3,
"target_midi_pitches": [
48
],
"rhythmic_flexibility": false
},
{
"offset": 4,
"target_midi_pitches": [
41
],
"rhythmic_flexibility": false
}
],
"exerciseId": "EA96YW",
"allowed_answers": [
"A",
"Bb",
"C",
"F",
"G"
],
"complexity_score": 1,
"staffDistribution": "bass"
}"""

ex = Exercise.objects.get(id='EA96YW')
ex.data = json.loads(json_data)
ex.save()
print("Restored EA96YW")
