#!/usr/bin/python

import sys
import re as reg
import os

if not sys.version_info[0] == 2:
    sys.exit("Sorry, this script is written for Python 2.")

original = './json/models/' + sys.argv[1] + '.json'
if not os.path.isfile(original):
    sys.exit('Model not found.')

schemata = []
schemata.append([
    '1', [
        [ 0, "jC_", ""],
        [-7, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [-7, "jF_", "b"],
        [ 0, "jC_", ""],
        [-5, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [-5, "jG_", "#"],
        [ 0, "jC_", ""],
    ]
])
schemata.append([
    '2', [
        [ 0, "jC_", ""],
        [-5, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [-5, "jG_", "#"],
        [ 0, "jC_", ""],
        [-7, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [-7, "jF_", "b"],
        [ 0, "jC_", ""],
    ]
])
schemata.append([
    '3', [
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [-5, "jG_", "#"],
        [ 0, "jC_", ""],
        [-7, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [-7, "jF_", "b"],
        [ 0, "jC_", ""],
        [-5, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
    ]
])
schemata.append([
    '4', [
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [-7, "jF_", "b"],
        [ 0, "jC_", ""],
        [-5, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [-5, "jG_", "#"],
        [ 0, "jC_", ""],
        [-7, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
    ]
])
schemata.append([# high
    '1', [
        [ 0, "jC_", ""],
        [ 5, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [ 5, "jF_", "b"],
        [ 0, "jC_", ""],
        [ 7, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [ 7, "jG_", "#"],
        [ 0, "jC_", ""],
    ]
])
schemata.append([# high
    '2', [
        [ 0, "jC_", ""],
        [ 7, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [ 7, "jG_", "#"],
        [ 0, "jC_", ""],
        [ 5, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [ 5, "jF_", "b"],
        [ 0, "jC_", ""],
    ]
])
schemata.append([# high
    '3', [
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [ 7, "jG_", "#"],
        [ 0, "jC_", ""],
        [ 5, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [ 5, "jF_", "b"],
        [ 0, "jC_", ""],
        [ 7, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
    ]
])
schemata.append([# high
    '4', [
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [ 5, "jF_", "b"],
        [ 0, "jC_", ""],
        [ 7, "jG_", "#"],
        [ 2, "jD_", "##"],
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [ 7, "jG_", "#"],
        [ 0, "jC_", ""],
        [ 5, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
    ]
])
schemata.append([
    '1', [
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [-3, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
    ]
])
schemata.append([
    '2', [
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [-3, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
    ]
])
schemata.append([
    '3', [
        [-3, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [-3, "iF#", "###"],
    ]
])
schemata.append([
    '4', [
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [-3, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
    ]
])
schemata.append([# high
    '1', [
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [ 9, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
    ]
])
schemata.append([# high
    '2', [
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [ 9, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
    ]
])
schemata.append([# high
    '3', [
        [ 9, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [ 9, "iF#", "###"],
    ]
])
schemata.append([# high
    '4', [
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"],
        [ 0, "iA_", ""],
        [ 7, "iE_", "#"],
        [ 2, "iB_", "##"],
        [ 9, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
    ]
])
schemata.append([# schema 17
    'flatward', [
        [-3, "jA_", "###"],
        [ 2, "jD_", "##"],
        [-5, "jG_", "#"],
        [ 0, "jC_", ""],
        [-7, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"]
    ]
])
schemata.append([# schema 18
    'flatward', [
        [-3, "iF#", "###"],
        [ 2, "iB_", "##"],
        [ 7, "iE_", "#"],
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"]
    ]
])
schemata.append([# schema 19
    'flats', [
        [ 0, "jC_", ""],
        [-7, "jF_", "b"],
        [-2, "jBb", "bb"],
        [ 3, "jEb", "bbb"],
        [-2, "jBb", "bb"],
        [-7, "jF_", "b"]
    ]
])
schemata.append([# schema 20
    'flats', [
        [ 0, "iA_", ""],
        [ 5, "iD_", "b"],
        [-2, "iG_", "bb"],
        [ 3, "iC_", "bbb"],
        [-2, "iG_", "bb"],
        [ 5, "iD_", "b"]
    ]
])

if sys.argv[2].isdigit():
    requested_schema = int(sys.argv[2])
    if not requested_schema in range(1, len(schemata) + 1):
        sys.exit('Schemata element out of range.')
    schemaIDs = [requested_schema - 1]
elif sys.argv[2] == "high":
    schemaIDs = [4, 5, 6, 7]
elif sys.argv[2] == "minor":
    schemaIDs = [8, 9, 10, 11]
elif sys.argv[2] == "minhigh":
    schemaIDs = [12, 13, 14, 15]
elif sys.argv[2] == "all":
    schemaIDs = [i for i in range(len(schemata))]
else:
    sys.exit('Unexpected input.')

print 'Applying schemas ' + str(schemaIDs)

for i in schemaIDs:
    suffix = schemata[i][0]
    schema = schemata[i][1]

    exDirectory = './json/all/' + sys.argv[1] + '_' + suffix + '/'
    if not os.path.exists(exDirectory):
        os.makedirs(exDirectory)

    semitones = 0
    def transpose(obj):
        val = int(obj.group(0))
        return str(val + semitones)

    with open(original, 'r') as f:
    	lines = f.readlines()

    exNum = 1
    for exercise in schema:
        output_lines = []
        jsonfile = exDirectory + '{number:0{width}d}'.format(width=2, number=exNum) + '.json'
        semitones = exercise[0]

        for i in range(len(lines)):
            line_gives_key = reg.match(r'^.*\"key\"', lines[i])
            line_gives_key_signature = reg.match(r'^.*\"keySignature\"', lines[i])
            line_has_MIDI_numbers = reg.match(r'^.*\"visible\"', lines[i])
            if line_has_MIDI_numbers:
            	nextline = reg.sub('\d+', transpose, lines[i])
            elif line_gives_key:
                nextline = '  "key": "' + exercise[1] + '",\n'
            elif line_gives_key_signature:
                nextline = '  "keySignature": "' + exercise[2] + '",\n'
            else:
                nextline = lines[i]
            output_lines.append(nextline)

        with open(jsonfile, 'w') as f:
        	for i in output_lines:
        		f.write(i)

        del output_lines

        exNum += 1
