# """
# Flesh out this Python script to transpose exercise content per a new text field in playlist admin.
# E.g. text field: `C e G c#'.
# Then populate playlist with each exercise in C major, E minor, G major, C# minor.
# Consider best approach.
# Either save needed transpositions in a separate section of database from original exercises
# or create dynamically.
# Exercise ID could look like EA00DD+16 or EA00DD-2 where you see the midi_vector.
#
# Once this works, add options:
# (1) loop transpositions per exercise,
# (2) loop transpositions per playlist,
# (3) shuffle transpositions per exercise (pseudo-random),
# (4) shuffle transpositions per playlist (pseudo-random).
#
# That is:
# (1) A+1,A+2,A+3,B+1,B+2,B+3
# (2) A+1,B+1,A+2,B+2,A+3,B+3
# (3) A+2,A+1,A+3,B+1,B+3,B+2
# (4) A+3,B+1,B+3,A+2,B+2,A+1
# """
from copy import deepcopy

from apps.exercises.constants import sig_to_pc, pseudo_key_to_sig, all_sigs, all_keys


def transpose(exercise, target_request):
    exercise = deepcopy(exercise)
    sig_orig = exercise.data.get('keySignature')
    pc_ref_orig = sig_to_pc[sig_orig]
    key_orig = exercise.data.get('key')
    try:
        sig_target = pseudo_key_to_sig[target_request]
    except KeyError:
        return exercise
        # abort this transposition, skip to next item in transpose_requests.split()

    pc_ref_target = sig_to_pc[sig_target]

    if key_orig == "h":
        key_target = key_orig
    else:
        # wrap these in try Except and abort transposition if error
        try:
            fifth_chain_move = all_sigs.index(sig_target) - all_sigs.index(sig_orig)
            key_target = all_keys[all_keys.index(key_orig) + 2 * fifth_chain_move]
        except IndexError:
            return exercise

    # 12 + not necessary here but keep it in case this function copied to Javascript
    pc_vector = (12 + pc_ref_target - pc_ref_orig) % 12

    # FIXME
    # midi_all_ex =  # get all midi numbers from json exercise chord subdictionaries (visible and hidden)
    midi_all_ex = []
    for chord in exercise.data['chord']:
        midi_max_ex = max(chord['visible'] + chord['hidden'])
        midi_min_ex = min(chord['visible'] + chord['hidden'])

    # midi_max_ex = max(midi_all_ex)
    # midi_min_ex = min(midi_all_ex)
    midi_mean_floor_ex = (midi_max_ex + midi_min_ex) // 2
    midi_range_ex = midi_max_ex + 1 - midi_min_ex

    # suitable for 88-key controllers, A0 to C8
    midi_mean_floor_target_min = 59
    if midi_range_ex <= 14:
        # suitable for 25-key controllers, C3 to C5
        midi_mean_floor_target_min = 54
    elif midi_range_ex <= 26:
        # suitable for 37-key controllers, C2 to C5
        midi_mean_floor_target_min = 48
    elif midi_range_ex <= 38:
        # suitable for 49-key controllers, C2 to C6
        midi_mean_floor_target_min = 54
    elif midi_range_ex <= 50:
        # suitable for 61-key controllers, C2 to C7
        midi_mean_floor_target_min = 60
    midi_mean_floor_target_range = range(midi_mean_floor_target_min, midi_mean_floor_target_min + 12)

    midi_vector = None
    octave_displ = 0
    arbitrary_limit = 7
    while octave_displ < arbitrary_limit and octave_displ > -arbitrary_limit:
        if (midi_mean_floor_ex + pc_vector + 12 * octave_displ) in midi_mean_floor_target_range:
            midi_vector = pc_vector + 12 * octave_displ
            break
        if octave_displ >= 0:
            octave_displ += 1
        octave_displ *= -1

    # FIXME
    if midi_vector == None:
        return exercise

    # WRITE TRANSPOSED EXERCISE: add midi_vector to all integers within json_data.chord and change
    # json_data.key = key_target and json_data.keySignature = sig_target
    for chord in exercise.data['chord']:
        transposed = [note + midi_vector for note in chord['visible']]
        chord.update(visible=transposed)

        transposed = [note + midi_vector for note in chord['hidden']]
        chord.update(hidden=transposed)

    exercise.data['key'] = key_target
    exercise.data['keySignature'] = sig_target

    exercise.id = f'{exercise.id}{midi_vector}'

    return exercise
