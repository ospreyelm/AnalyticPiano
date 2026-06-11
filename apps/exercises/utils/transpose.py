# """
# Transpose exercise content per a new text field in playlist editor.
#
# User input example: `C G c#'
# Result: populate playlist with each exercise in 0, 1, 4 sharps
#
# The distinction of major and minor is immaterial; this is a convenient shorthand.
#
# Exercise ID will appear as EA00DD+16 or EA00DD-2 where you see the midi_vector.
#
# Options:
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


def normalize_key(k):
    """Converts a Clean key (e.g., 'D', 'Bb', 'F#m') to HarmonyLab format (e.g., 'jD_', 'jBb', 'iF#')."""
    if not k or k == "h" or k in all_keys:
        return k
    is_minor = k.endswith('m')
    prefix = 'i' if is_minor else 'j'
    note = k[:-1] if is_minor else k
    # Add underscore suffix for natural pitch names
    suffix = "_" if ("#" not in note and "b" not in note) else ""
    return prefix + note + suffix


def compute_midi_vector(sig_orig, sig_target, midi_notes=None):
    """Compute the signed MIDI transposition interval from sig_orig to sig_target.

    Picks the direction that results in the smallest interval (<=6 semitones),
    matching the 'shortest-interval' rule used in transpose().  The midi_notes
    argument is accepted for API symmetry (future: could enable the
    keyboard-range octave-fitting heuristic inside transpose()) but is not
    used in the current implementation.

    Returns (midi_vector: int, key_target: None).
    key_target is always None — call compute_key_target() separately to
    resolve the target HarmonyLab key token.  Returns (0, None) when
    sig_target is not in all_sigs.
    """
    if sig_target not in all_sigs:
        return (0, None)

    pc_ref_orig = sig_to_pc[sig_orig]
    pc_ref_target = sig_to_pc[sig_target]
    pc_vector = (12 + pc_ref_target - pc_ref_orig) % 12

    # Shortest-interval rule: prefer going down for intervals >= 6 semitones.
    # Tritone (exactly 6) prefers down — identical to transpose().
    if pc_vector >= 6:
        midi_vector = pc_vector - 12
    else:
        midi_vector = pc_vector

    return (midi_vector, None)


def compute_key_target(key_orig, sig_orig, sig_target):
    """Return the HarmonyLab key token after transposing from sig_orig to sig_target.

    key_orig must already be in HarmonyLab format (e.g. 'jC_').  Returns None
    when the computation is out of range.
    """
    if sig_target not in all_sigs:
        return None
    if key_orig == "h":
        return key_orig
    try:
        fifth_chain_move = all_sigs.index(sig_target) - all_sigs.index(sig_orig)
        return all_keys[all_keys.index(key_orig) + 2 * fifth_chain_move]
    except (ValueError, IndexError):
        return None


def transpose(exercise, staff_sig_request):
    exercise = deepcopy(exercise)
    sig_orig = exercise.data.get("keySignature")
    key_orig = exercise.data.get("key")
    
    # Handle human-readable tonic names (e.g. 'D', 'Bb') by converting to accidental strings
    if sig_orig in pseudo_key_to_sig:
        sig_orig = pseudo_key_to_sig[sig_orig]
        
    # Handle clean key names for circle-of-fifths index lookups
    key_orig = normalize_key(key_orig)
    
    pc_ref_orig = sig_to_pc[sig_orig]
    if staff_sig_request not in all_sigs:
        return exercise
        # Bogus requests should never get this far, due to Django validation
        # of tranpose_requests and tests in transposition_matrix.
        # If they did, returning the untransposed exercise more than once
        # would cause grading problems.

    pc_ref_target = sig_to_pc[staff_sig_request]

    if key_orig == "h":
        key_target = key_orig
    else:
        try:
            fifth_chain_move = all_sigs.index(staff_sig_request) - all_sigs.index(sig_orig)
            key_target = all_keys[all_keys.index(key_orig) + 2 * fifth_chain_move]
        except IndexError:
            return exercise
            # ditto comment on return statement above

    # 12 + not necessary here but keep it in case this function copied to Javascript
    pc_vector = (12 + pc_ref_target - pc_ref_orig) % 12

    midi_all_ex = []
    # FIX: Safety check for 'chord' list
    if "chord" in exercise.data and exercise.data["chord"]:
        for chord in exercise.data["chord"]:
            midi_all_ex.extend(chord.get("visible", []) + chord.get("hidden", []))

    if midi_all_ex:
        midi_max_ex = max(midi_all_ex)
        midi_min_ex = min(midi_all_ex)
        midi_mean_floor_ex = (midi_max_ex + midi_min_ex) // 2
        midi_range_ex = midi_max_ex + 1 - midi_min_ex

        # suitable for 88-key controllers, A0 to C8
        midi_mean_floor_target_min = 59
        if midi_range_ex <= 14:
            # suitable for 25-key controllers, C3 to C5
            midi_mean_floor_target_min = 54
        elif midi_range_ex <= 21:
            # suitable for 32-key controllers, 8vb, F2 to C5
            # Arturia, Midiplus, Native Instruments
            midi_mean_floor_target_min = 51
        elif midi_range_ex <= 26:
            # suitable for 37-key controllers, 8vb, C2 to C5
            midi_mean_floor_target_min = 48
        elif midi_range_ex <= 38:
            # suitable for 49-key controllers, C2 to C6
            midi_mean_floor_target_min = 54
        elif midi_range_ex <= 50:
            # suitable for 61-key controllers, C2 to C7
            midi_mean_floor_target_min = 60
        midi_mean_floor_target_range = range(
            midi_mean_floor_target_min, midi_mean_floor_target_min + 12
        )

        midi_vector = None

        if False:
            # TODO: enable this as an option in the playlist transposition controls
            # algorithm that fits exercise onto smallest standard keyboard
            # that will accommodate all keys
            octave_displ = 0
            arbitrary_limit = 7
            while octave_displ < arbitrary_limit and octave_displ > -arbitrary_limit:
                if (
                    midi_mean_floor_ex + pc_vector + 12 * octave_displ
                ) in midi_mean_floor_target_range:
                    midi_vector = pc_vector + 12 * octave_displ
                    break
                if octave_displ >= 0:
                    octave_displ += 1
                octave_displ *= -1
        else:
            # Pick the direction that results in the smaller interval (≤ 6 semitones).
            # For exactly 6 semitones (tritone), prefer going down.
            if pc_vector >= 6:
                midi_vector = pc_vector - 12  # go down instead
            else:
                midi_vector = pc_vector
    else:
        # If no chords, we just shift by the base pc_vector without range optimization
        midi_vector = pc_vector
        if pc_vector >= 6:
            midi_vector = pc_vector - 12

    # make the transposition
    if "chord" in exercise.data:
        for chord in exercise.data["chord"]:
            if "visible" in chord:
                chord["visible"] = [note + midi_vector for note in chord["visible"]]
            if "hidden" in chord:
                chord["hidden"] = [note + midi_vector for note in chord["hidden"]]

    exercise.data["key"] = key_target
    exercise.data["keySignature"] = staff_sig_request

    # Only update ID if we actually moved anything
    if midi_vector != 0:
        exercise.id = f"{exercise.id}{midi_vector}"

    return exercise
