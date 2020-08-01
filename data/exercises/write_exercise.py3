#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import re as reg

print ("\n*** HarmonyLab Exercise-Authoring Tool ***\n")



# Default menu selections for interactive mode

menu_1 = "3"
menu_2 = "3"
menu_3 = "3"
menu_4 = "3"
menu_5 = "5"

# Layout modes for dynamic interactive menu

staff_distributions = [
    "keyboard",
    "chorale",
    "LH",
    "RH",
    "keyboardPlusRHBias"
]

# Consult user

if reg.match(r'.+\.txt', sys.argv[-1]):
    # Gather inputs from a text file

    with open(sys.argv[-1], "r", encoding="utf-8") as f:
        simulated_inputs = [i.strip() for i in f.readlines()]
    if len(simulated_inputs) >= 12:
        exercise_prompt = simulated_inputs[0]
        tonality_input = simulated_inputs[1]
        staff_signature_input = simulated_inputs[2]
        chords_input = simulated_inputs[3]
        review_text = simulated_inputs[4]
        directory = simulated_inputs[5]
        basename = simulated_inputs[6]
        menu_1 = simulated_inputs[7]
        menu_2 = simulated_inputs[8]
        menu_3 = simulated_inputs[9]
        menu_4 = simulated_inputs[10]
        menu_5 = simulated_inputs[11]

else:
    # Gather inputs interactively in the terminal

    exercise_prompt = input ("Write an EXERCISE PROMPT: ")

    print ("\nTime to specify a key. Examples:" +
        '\n\t"Bb" --> B-flat major' +
        '\n\t"g" --> G minor' +
        '\n\t"A" --> A major' +
        '\n\t"f#" --> F-sharp minor' +
        '\n\t"" (i.e. empty) --> no key\n')
    tonality_input = input ("What is the KEY? ")
    print ()

    print ("Time to specify a key signature. Examples:" +
        '\n\t"=" --> match the tonality' +
        '\n\t"##" --> two sharps' +
        '\n\t"bbbb" --> four flats' +
        '\n\t"" --> no sharps or flats\n')
    staff_signature_input = input ("What is the KEY SIGNATURE? ")
    print ()

    print ('''Enter chords. Use the format shown, prefixing "x" or "." 
to notes that the student will be expected to match without seeing 
them notated. (Pitches follow Lilypond in English or Dutch, or 
plain lowercase English using accidentals "b", "#", "bb", "x".) 
Use the relative pitch styling from Lilypond.''' +
        "\n\n\t\"<>\" to enclose each sonority (including single melodic notes)" +
        "\n\t\"c'\" for C4 (middle C), \"c''\" for C5, etc." +
        "\n\t\"c\" for C3, \"c,\" for C2, \"c,,\" for C1 etc." +
        "\n\tExample: <a, a' c e> <e' xg# b e>")
    print ()

    print ('''IMPORTANT: HarmonyLab will not heed your enharmonic spelling 
when rendering the exercises. Authors should check that HarmonyLab spells the 
chosen chords as desired.''')
    print ()

    chords_input = input ("Type CHORDS: ")
    print ()

    review_text = input ("Write a CONGRATULATION: ")
    print ()

    directory = input ('Specify the DIRECTORY (use "." or "" for testing or "M" for the models directory): ')
    print ()

    basename = input ('Specify the BASENAME (i.e. exercise number): ')
    print ()

    print ("Choose what note names to display:" +
        "\n\t[1] note names" +
        "\n\t[2] scientific pitch notation" +
        "\n\t[3] neither")
    selection = input ("Selection: ")
    if selection in ["1", "2", "3"]:
        menu_1 = selection
    else:
        print ("Invalid selection. Default retained.")
    del selection
    print ()

    print ("Choose what melodic analysis to display:" +
        "\n\t[1] scale degrees" +
        "\n\t[2] solfege" +
        "\n\t[3] neither")
    selection = input ("Selection: ")
    if selection in ["1", "2", "3"]:
        menu_2 = selection
    else:
        print ("Invalid selection. Default retained.")
    del selection
    print ()

    print ("Choose what harmonic analysis to display:" +
        "\n\t[1] Roman numerals" +
        "\n\t[2] intervals" +
        "\n\t[3] neither" +
        "\n\t[4] both")
    selection = input ("Selection: ")
    if selection in ["1", "2", "3", "4"]:
        menu_3 = selection
    else:
        print ("Invalid selection. Default retained.")
    del selection
    print ()

    print ("Choose what highlights to display:" +
        "\n\t[1] roots" +
        "\n\t[2] tritones" +
        "\n\t[3] neither" +
        "\n\t[4] both")
    selection = input ("Selection: ")
    if selection in ["1", "2", "3", "4"]:
        menu_4 = selection
    else:
        print ("Invalid selection. Default retained.")
    del selection
    print ()

    print ("Choose how to distribute notes between staves:")
    i = 0
    while i < len(staff_distributions):
        print ("\t[" + str(i + 1) + "] " + staff_distributions[i])
        i += 1
    del i
    selection = input ("Selection: ")
    if selection in [str(i + 1) for i in range(len(staff_distributions))]:
        menu_5 = selection
    else:
        print ("Invalid selection. Default retained.")     
    del selection




# Process information

exercise_prompt = reg.sub(r'"\b', '“', exercise_prompt)
exercise_prompt = reg.sub(r'\b"', '”', exercise_prompt)

tonalities = {
    "ab": "iAb",
    "eb": "iEb",
    "bb": "iBb",
    "f": "iF_",
    "c": "iC_",
    "g": "iG_",
    "d": "iD_",
    "a": "iA_",
    "e": "iE_",
    "b": "iB_",
    "f#": "iF#",
    "c#": "iC#",
    "g#": "iG#",
    "d#": "iD#",
    "a#": "iA#",
    "Cb": "jCb",
    "Gb": "jGb",
    "Db": "jDb",
    "Ab": "jAb",
    "Eb": "jEb",
    "Bb": "jBb",
    "F": "jF_",
    "C": "jC_",
    "G": "jG_",
    "D": "jD_",
    "A": "jA_",
    "E": "jE_",
    "B": "jB_",
    "F#": "jF#",
    "C#": "jC#",
    "": "h",
    "h": "h"
}

signatures_per_tonalities = {
    "iAb": "bbbbbbb",
    "iEb": "bbbbbb",
    "iBb": "bbbbb",
    "iF_": "bbbb",
    "iC_": "bbb",
    "iG_": "bb",
    "iD_": "b",
    "iA_": "",
    "iE_": "#",
    "iB_": "##",
    "iF#": "###",
    "iC#": "####",
    "iG#": "#####",
    "iD#": "######",
    "iA#": "#######",
    "jCb": "bbbbbbb",
    "jGb": "bbbbbb",
    "jDb": "bbbbb",
    "jAb": "bbbb",
    "jEb": "bbb",
    "jBb": "bb",
    "jF_": "b",
    "jC_": "",
    "jG_": "#",
    "jD_": "##",
    "jA_": "###",
    "jE_": "####",
    "jB_": "#####",
    "jF#": "######",
    "jC#": "#######",
    "h": ""
}

tonality = tonalities[tonality_input]

if staff_signature_input == "=":
    staff_signature = signatures_per_tonalities[tonality]
else:
    staff_signature = staff_signature_input

del tonalities, signatures_per_tonalities



# START OF CODE FOR CHORDS

# Necessary dictionaries and arrays

pitch_classes = {
    # spelled for D minor, plain English
    "c": 0,
    "c#": 1,
    "d": 2,
    "eb": 3,
    "e": 4,
    "f": 5,
    "f#": 6,
    "g": 7,
    "g#": 8,
    "a": 9,
    "bb": 10,
    "b": 11,

    # spelled for D minor, Lilypond English
    "c": 0,
    "cs": 1,
    "d": 2,
    "ef": 3,
    "e": 4,
    "f": 5,
    "fs": 6,
    "g": 7,
    "gs": 8,
    "a": 9,
    "bf": 10,
    "b": 11,

    # spelled for D minor, Lilypond Dutch
    "c": 0,
    "cis": 1,
    "d": 2,
    "es": 3,
    "ees": 3,
    "e": 4,
    "f": 5,
    "fis": 6,
    "g": 7,
    "gis": 8,
    "a": 9,
    "bes": 10,
    "b": 11,

    # spelled for other than D minor, plain English
    "b#": 0,
    "db": 1,
    "c##": 2,
    "cx": 2,
    "d#": 3,
    "d##": 4,
    "dx": 4,
    "fb": 4,
    "e#": 5,
    "gb": 6,
    "f##": 7,
    "fx": 7,
    "ab": 8,
    "g##": 9,
    "gx": 9,
    "bbb": 9,
    "a#": 10,
    "cb": 11,

    # spelled for other than D minor, Lilypond English
    "bs": 0,
    "df": 1,
    "css": 2,
    "ds": 3,
    "dss": 4,
    "ff": 4,
    "es": 5,
    "gf": 6,
    "fss": 7,
    "af": 8,
    "gss": 9,
    "bff": 9,
    "as": 10,
    "cf": 11,

    # spelled for other than D minor, Lilypond Dutch
    "bis": 0,
    "des": 1,
    "cisis": 2,
    "dis": 3,
    "disis": 4,
    "fes": 4,
    "eis": 5,
    "ges": 6,
    "fisis": 7,
    "aes": 8,
    "gisis": 9,
    "beses": 9,
    "ais": 10,
    "ces": 11,
}

jumps_up = [
    ["g", "c"],
    ["a", "d"],
    ["b", "e"],
    ["a", "c"],
    ["b", "d"],
    ["b", "c"],
]

jumps_down = [
    ["e", "b"],
    ["d", "a"],
    ["c", "g"],
    ["d", "b"],
    ["c", "a"],
    ["c", "b"],
]



# Functions for chord parsing

def get_rhythm_code(lilypond_rhythm_id):
    # The app has limited rhythmic capabilities
    if lilypond_rhythm_id == "1":
        return "w"
    elif lilypond_rhythm_id == "2":
        return "h"
    elif lilypond_rhythm_id == "4":
        return "q"
    else:
        return ""

def get_relative_octave(pitch, suffix, reference_pitch):
    relative_octave = 0

    suffix = reg.sub("’", "'", suffix) # replace curly apostrophes
    if reg.match(r"^'+$", suffix):
        relative_octave += len(suffix)
    elif reg.match(r"^,+$", suffix):
        relative_octave -= len(suffix)
    else:
        relative_octave = 0

    if [reference_pitch[0], pitch[0]] in jumps_up:
        relative_octave += 1
    if [reference_pitch[0], pitch[0]] in jumps_down:
        relative_octave -= 1

    return relative_octave

def get_pitch_parameter(pitch, parameter):
    # Unsure how foolproof this is
    match = reg.search(r"([a-gis#]+x?)([’',]*)", pitch)
    if parameter == "name":
        return match.group(1)
    if parameter == "suffix":
        return match.group(2)
    if parameter == "pc":
        return pitch_classes[match.group(1)]

def midi(pitch_class, absolute_octave):
    # middle C (C4) is MIDI # 60
    # C0 is MIDI # 12
    return int(12 + absolute_octave * 12 + pitch_class)



# Translate input for the app

chords = reg.split(r' *<', chords_input)
for i in reversed(range(len(chords))):
    # put chords in an array
    if chords[i] == "":
        chords.pop(i)
for i in range(len(chords)):
    # separate pitch and rhythm
    chords[i] = reg.split(r' *> *', chords[i])
    # limit datapoints to two, just in case
    chords[i] = chords[i][:2]
for i in range(1, len(chords)):
    # make rhythm explicit
    if chords[i][1] == "":
        chords[i][1] = chords[i - 1][1]
for i in range(len(chords)):
    # translate rhythm for the app
    chords[i][1] = get_rhythm_code(chords[i][1])
for i in range(len(chords)):
    # for the pitch component of each chord, put pitches in an array
    # this could be rewritten as a method
    chord = chords[i][0]
    # x or . prefixed to a pitch will send it to hidden
    chord = reg.sub(r'([x.]) *([a-g])', r'\1\2', chord)
    chord = reg.split(r' +', chord)
    for j in range(len(chord)):
        # express each pitch as a pair (visibility, pitch)
        # this could be rewritten as a method
        pitch = chord[j]
        if len(pitch) == 0:
            # chord is empty
            break
        if pitch[0] in ["x", "."]:
            pitch = ["hidden", pitch[1:]]
        else:
            pitch = ["visible", pitch]
        chord[j] = pitch

    chords[i][0] = chord

reference_octaves = [3, 3]
reference_pitches = ["f", "f"]

for i in range(len(chords)):
    
    # for the pitch component of each chord
    chord = chords[i][0]

    for j in range(len(chord)):

        if len(chord[j]) == 0:
            # chord is empty
            break

        # for the pitch element of each (visibility, pitch) pair
        pitch = chord[j][1]

        # find position
        ref_branch = 1 # inside each chord
        if j == 0:
            ref_branch = 0 # reaching back to the start of previous chord

        relative_octave = get_relative_octave(
            get_pitch_parameter(pitch, "name"),
            get_pitch_parameter(pitch, "suffix"),
            reference_pitches[ref_branch]
        )

        abs_octave = relative_octave + reference_octaves[ref_branch]

        # remember position
        if j == 0:
            reference_octaves[0] = abs_octave
            reference_pitches[0] = get_pitch_parameter(pitch, "name")

        reference_octaves[1] = abs_octave
        reference_pitches[1] = get_pitch_parameter(pitch, "name")

        # overwrite pitch with MIDI number
        chord[j][1] = midi(get_pitch_parameter(pitch, "pc"), abs_octave)

    chords[i][0] = chord

json_chords = []

for i in range(len(chords)):

    rhythm_value = chords[i][1]

    # sort pitches into visible and hidden
    visible = []
    hidden = []

    for pitch in chords[i][0]:
        if len(pitch) == 0:
            # empty chord
            break
        if pitch[0] == "visible":
            visible.append(pitch[1])
        if pitch[0] == "hidden":
            hidden.append(pitch[1])

    visible = sorted(visible)
    hidden = sorted(visible)

    # translate for app
    json_chords.append({"visible": visible, "hidden": hidden, "rhythmValue": rhythm_value})

# END OF CODE FOR CHORDS



review_text = reg.sub(r'"\b', '“', review_text)
review_text = reg.sub(r'\b"', '”', review_text)

basename_input = basename
if basename == "":
    basename = "auto"

if directory == "." or directory == "":
    json_path = "./" + basename + ".json"
    # The following file will be an archive of the interactive user inputs
    text_archive_path = "./" + basename + "_archive.txt"
elif directory == "M":
    json_path = "./json/models/" + basename + ".json"
    text_archive_path = "./txt/models" + basename + "_archive.txt"
else:
    json_path = "./json/all/" + directory + "/" + basename + ".json"
    text_archive_path = "./txt/all" + directory + "/" + basename + "_archive.txt"

note_names = menu_1 == 1
scientific_pitch = menu_1 == 2

scale_degrees = menu_2 == 1
solfege = menu_2 == 2

roman_numerals = menu_3 in [1, 4]
intervals = menu_3 in [2, 4]

root_highlight = menu_4 in [1, 4]
tritone_highlight = menu_4 in [2, 4]

staff_distribution = staff_distributions[int(menu_5) - 1]



# Write files

text_archive_content = exercise_prompt + "\n" + \
    tonality_input + "\n" + \
    staff_signature_input + "\n" + \
    chords_input + "\n" + \
    review_text + "\n" + \
    directory + "\n" + \
    basename_input + "\n" + \
    menu_1 + "\n" + \
    menu_2 + "\n" + \
    menu_3 + "\n" + \
    menu_4 + "\n" + \
    menu_5

os.makedirs(os.path.dirname(text_archive_path), exist_ok=True)
with open(text_archive_path, "w", encoding="utf-8") as f:
    f.write(text_archive_content)

json_chords_str = "[\n    " + \
    ",\n    ".join([str(i) for i in json_chords]) + "\n  ]"

json_chords_str = reg.sub("'", "\"", json_chords_str)

json_content = '''{
  "type": "matching",
  "introText": "''' + exercise_prompt + '''",
  "keySignature": "''' + staff_signature + '''",
  "key": "''' + tonality + '''",
  "chord": ''' + json_chords_str + ''',
  "reviewText": "''' + review_text + '''",
  "staffDistribution": "''' + staff_distribution + '''",
  "analysis": {
    "enabled": true,
    "mode": {
      "note_names": ''' + str(note_names).lower() + ''',
      "scientific_pitch": ''' + str(scientific_pitch).lower() + ''',
      "scale_degrees": ''' + str(scale_degrees).lower() + ''',
      "solfege": ''' + str(solfege).lower() + ''',
      "roman_numerals": ''' + str(roman_numerals).lower() + ''',
      "intervals": ''' + str(intervals).lower() + '''
    }
  },
  "highlight": {
    "enabled": true,
    "mode": {
      "roothighlight": ''' + str(root_highlight).lower() + ''',
      "tritonehighlight": ''' + str(tritone_highlight).lower() + '''
    }
  }
}'''

os.makedirs(os.path.dirname(json_path), exist_ok=True)
with open(json_path, "w", encoding="utf-8") as f:
    f.write(json_content)

message = "The following content was written to " + json_path
print ()
print (message)
print ("*" * len(message))
print (json_content)
