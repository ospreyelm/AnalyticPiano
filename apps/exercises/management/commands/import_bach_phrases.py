import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from music21 import corpus, stream, note, chord, meter, key
from music21.expressions import Fermata

from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.utils.m21_cir_converter import m21_to_cir
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills




def _description_exists(description: str, authored_by=None) -> bool:
    from apps.exercises.models import Exercise
    qs = Exercise.objects.filter(description=description)
    if authored_by is not None:
        qs = qs.filter(authored_by=authored_by)
    return qs.exists()


def _declared_score_key(score):
    """Return the chorale's declared key before falling back to analysis."""
    declared = sorted(
        score.recurse().getElementsByClass(key.Key),
        key=lambda k: k.getOffsetInHierarchy(score),
    )
    if declared:
        return declared[0]
    return score.analyze('key')


def _apply_suspension_figures(overrides: list, figured_by_offset: dict | None = None) -> list:
    """Rewrite abbreviated figures for suspension/resolution pairs."""
    ordered = sorted(overrides, key=lambda o: o["offset"])
    figured_offsets = sorted(figured_by_offset) if figured_by_offset else []
    for idx, current in enumerate(ordered):
        current_content = current.get("content", {})
        if figured_by_offset:
            next_content = None
            for offset in figured_offsets:
                if offset > current["offset"] + 1e-6:
                    next_content = figured_by_offset[offset]
                    break
            if next_content is None:
                continue
        elif idx + 1 < len(ordered):
            next_content = ordered[idx + 1].get("content", {})
        else:
            continue
        if (
            current_content.get("raw_figured_bass") == "8/7/4"
            and next_content.get("raw_figured_bass") == "8/7/3"
        ):
            current_content["figured_bass"] = "7/4-3"
    return overrides


def _build_roman_analysis_overrides(
    phrase_score,
    global_key,
    unit_tags: list,
    riemenschneider: int,
) -> list:
    """Analyze a phrase and return UMTO analysis_overrides with WiR Roman numerals.

    Emits a slice for every chordify beat (matching the score window grid).
    WiR label used when available; NCT beats get all-null content so the
    frontend's allContentNull check hides them without breaking slot alignment.
    Raises CommandError if the chorale is not in the WiR corpus.
    """
    from music21.roman import romanNumeralFromChord
    from apps.exercises.utils import wir_corpus

    if not wir_corpus.has_chorale(riemenschneider):
        raise CommandError(
            f"Riemenschneider {riemenschneider} not found in When in Rome corpus. "
            f"Only standalone chorales (1-371) are supported in roman mode."
        )

    chorded = phrase_score.chordify()
    measures = list(chorded.getElementsByClass('Measure'))
    if not measures:
        return []

    first_measure_offset = measures[0].offset
    overrides = []
    seen_offsets = set()
    figured_by_offset = {
        override["offset"]: override["content"]
        for override in _build_figured_bass_overrides(phrase_score, global_key)
    }

    for m in measures:
        measure_start = m.offset - first_measure_offset
        for element in m.flat.notes:
            if not isinstance(element, chord.Chord):
                continue
            abs_offset = round(measure_start + float(element.offset), 5)
            if abs_offset in seen_offsets:
                continue
            seen_offsets.add(abs_offset)

            wir_result = wir_corpus.lookup(
                riemenschneider,
                element.measureNumber,
                float(element.beat),
            )

            try:
                rn = romanNumeralFromChord(element, global_key)
                figure = rn.figure
            except Exception:
                figure = None

            figured_content = figured_by_offset.get(abs_offset, {})
            raw_figured_bass = figured_content.get("raw_figured_bass")
            figured_bass = figured_content.get("figured_bass")

            if wir_result is not None:
                content = {
                    "roman_numeral": wir_result["label"],
                    "local_key": wir_result["local_key"],
                    "raw_roman_numeral": figure,
                    "raw_figured_bass": raw_figured_bass,
                    "figured_bass": figured_bass,
                    "pop_symbol": None,
                    "functional_label": None,
                }
            else:
                # No WiR label at this beat (NCT / passing-tone). Preserve the
                # derived figured-bass values so the harmonization grader can
                # build an accurate target from the actual sounding chord.
                # Display-side filtering of non-standard figures is the
                # frontend's job — do not null these here.
                content = {
                    "roman_numeral": None,
                    "local_key": None,
                    "raw_roman_numeral": figure,
                    "raw_figured_bass": raw_figured_bass,
                    "figured_bass": figured_bass,
                    "pop_symbol": None,
                    "functional_label": None,
                }

            overrides.append({
                "offset": abs_offset,
                "content": content,
                "unit_tags": list(unit_tags),
            })

    return _apply_suspension_figures(overrides, figured_by_offset)


def _phrase_has_silent_measure(phrase_score) -> bool:
    """True when phrase contains a measure whose notes fill less than
    half its bar duration. Anacrusis (pickup) measures are exempted —
    music21 marks them with paddingLeft > 0 and their content is
    intentionally shorter than the bar.
    """
    for m_test in phrase_score.parts[0].getElementsByClass(stream.Measure):
        if m_test.paddingLeft and m_test.paddingLeft > 0:
            continue
        notes_ql = sum(n.quarterLength for n in m_test.flatten().notes)
        bar_ql = m_test.barDuration.quarterLength
        if bar_ql > 0 and notes_ql < bar_ql * 0.5:
            return True
    return False


def _build_next_pitch_map(phrase_score) -> dict[float, dict[int, int]]:
    """Build a per-offset map of {midi: next_midi} for each sounding pitch.

    For each absolute offset in the score, maps each pitch's MIDI number to the
    MIDI number of the next note in the same voice (part). Used by
    compute_figured_bass to distinguish 9ths (resolve down) from 2nds (stay/rise).
    Tied notes are treated as staying in place (next_midi == current_midi).
    """
    from music21 import note as m21note, chord as m21chord

    # per_voice_timeline[part_index] = sorted list of (abs_offset, midi)
    voice_timelines = []
    for part in phrase_score.parts:
        timeline = []
        for el in part.flatten().notes:
            abs_off = round(float(el.offset), 5)
            if isinstance(el, m21note.Note):
                # Tied-stop notes: voice is "staying" — treat as same pitch
                midi = el.pitch.midi
                timeline.append((abs_off, midi))
            elif isinstance(el, m21chord.Chord):
                for p in el.pitches:
                    timeline.append((abs_off, p.midi))
        timeline.sort(key=lambda x: x[0])
        voice_timelines.append(timeline)

    # For each (offset, midi) find the next different offset in the same part
    # result[abs_offset][midi] = next_midi
    result: dict[float, dict[int, int]] = {}
    for timeline in voice_timelines:
        for i, (off, midi) in enumerate(timeline):
            # Find next entry in this part at a strictly later offset
            next_midi = midi  # default: stays (tie or end of phrase)
            for j in range(i + 1, len(timeline)):
                if timeline[j][0] > off + 1e-6:
                    next_midi = timeline[j][1]
                    break
            if off not in result:
                result[off] = {}
            result[off][midi] = next_midi

    return result


def _build_figured_bass_overrides(phrase_score, global_key) -> list:
    """Analyze a phrase and return UMTO analysis_overrides with figured bass.

    # TODO: suspension detection (4-3, 7-6, 9-8) — requires look-ahead
    # over consecutive offsets. Deferred to a follow-on task.

    Stores raw_figured_bass (unabbreviated stack) and figured_bass (Kellner-
    abbreviated). roman_numeral and raw_roman_numeral are left null — this
    function is only called for mode:figures and mode:figures_unabbreviated.
    Targeting (curriculum filtering) happens at request time in
    generate_exercise_context; nothing is filtered here.
    """
    from music21 import chord
    from apps.exercises.utils.figured_bass import compute_figured_bass

    chorded = phrase_score.chordify()
    measures = list(chorded.getElementsByClass('Measure'))
    if not measures:
        return []

    next_pitch_context = _build_next_pitch_map(phrase_score)

    first_measure_offset = measures[0].offset
    overrides = []
    seen_offsets = set()

    for m in measures:
        measure_start = m.offset - first_measure_offset
        for element in m.flatten().notes:
            if not isinstance(element, chord.Chord):
                continue
            abs_offset = round(measure_start + float(element.offset), 5)
            if abs_offset in seen_offsets:
                continue
            seen_offsets.add(abs_offset)
            try:
                next_map = next_pitch_context.get(abs_offset)
                raw_fb, abbrev_fb = compute_figured_bass(element, global_key,
                                                         next_pitch_map=next_map)
            except Exception:
                raw_fb, abbrev_fb = None, None

            overrides.append({
                "offset": abs_offset,
                "content": {
                    "roman_numeral": None,
                    "raw_roman_numeral": None,
                    "raw_figured_bass": raw_fb,
                    "figured_bass": abbrev_fb,
                    "pop_symbol": None,
                    "functional_label": None,
                },
            })

    return _apply_suspension_figures(overrides)


class Command(BaseCommand):
    help = 'Import a Bach chorale and split it into phrases based on fermatas.'

    def add_arguments(self, parser):
        parser.add_argument('--bwv', type=int, help='BWV number (e.g. 1)')
        parser.add_argument('--movement', type=int, help='Movement number (e.g. 6)')
        parser.add_argument('--riemenschneider', type=int, help='Riemenschneider number (e.g. 1-371)')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--mode', type=str, choices=['play', 'play_figures', 'roman', 'figures', 'figures_unabbreviated', 'matching'], default='play', help='Exercise mode')
        parser.add_argument('--min-measures', type=int, default=3, help='Minimum measures per phrase')
        parser.add_argument('--dry-run', action='store_true', help='Show phrase ranges without creating exercises')
        parser.add_argument('--public', action='store_true', help='Mark imported exercises as public')
        parser.add_argument('--extra-tags', nargs='*', default=[], metavar='TAG',
                            help='Additional skill tags stamped on every imported exercise')
        parser.add_argument('--overwrite', action='store_true',
                            help='Update existing exercises (matched by description+author) instead of skipping')

    def handle(self, *args, **options):
        bwv_num = options.get('bwv')
        movement_num = options.get('movement')
        riem_num = options.get('riemenschneider')
        author_email = options['author']
        mode = options['mode']
        min_measures = options['min_measures']
        dry_run = options['dry_run']
        overwrite = options['overwrite']

        if mode in ('roman', 'matching', 'play', 'play_figures'):
            from apps.exercises.utils import wir_corpus
            if riem_num is not None:
                if not wir_corpus.has_chorale(riem_num):
                    raise CommandError(
                        f"Riemenschneider {riem_num} not found in When in Rome corpus. "
                        f"Only standalone chorales (1-371) are supported in WiR-backed modes."
                    )
            elif bwv_num is not None:
                riem_num = wir_corpus.bwv_to_riemenschneider(str(bwv_num))
                if riem_num is None:
                    raise CommandError(f"BWV {bwv_num} not in When in Rome corpus.")

        # 1. Load the score
        from music21 import corpus
        if riem_num:
            self.stdout.write(f"Loading Riemenschneider Chorale #{riem_num}...")
            # Use the Iterator to get the stream for the specific number
            from music21.corpus import chorales
            iterator = chorales.Iterator(riem_num, riem_num, numberingSystem='riemenschneider')
            # The iterator behaves like a list where you might need to convert to list or iterate
            score = list(iterator)[0]
            bwv_display = f"R{riem_num}"
            # Extract actual BWV number if available in metadata
            try:
                actual_bwv = score.metadata.number if hasattr(score.metadata, 'number') else None
                if actual_bwv:
                    bwv_num = int(actual_bwv)
            except:
                pass
        elif bwv_num and movement_num:
            self.stdout.write(f"Loading BWV {bwv_num}.{movement_num}...")
            score = corpus.parse('bach/bwv' + str(bwv_num) + '.' + str(movement_num))
            bwv_display = str(bwv_num)
        else:
            raise CommandError("Must provide either --riemenschneider OR both --bwv and --movement")

        # 1. Validate Author
        User = get_user_model()
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        if not score:
            raise CommandError("Could not load score")

        # 2. Cadence Detection (Harmonic + Rhythmic Heuristic)
        self.stdout.write("Analyzing harmonic arrivals and rhythmic cadences...")
        try:
            score_key = _declared_score_key(score)
            cadence_key = score.analyze('key')
            # chordify is heavy, but necessary for vertical analysis
            chorded = score.chordify()
        except Exception as e:
            raise CommandError(f"Analysis failed: {e}")

        fermata_measures = []
        measures = list(chorded.getElementsByClass('Measure'))
        
        last_split_m = measures[0].number - 1
        for i, m in enumerate(measures):
            m_notes = m.flat.notes
            if not m_notes:
                continue
                
            last_chord = m_notes[-1]
            if not isinstance(last_chord, chord.Chord):
                continue

            # How long since the last split?
            measures_since_split = m.number - last_split_m
            
            # Harmonic Check
            from music21.roman import romanNumeralFromChord
            rn = romanNumeralFromChord(last_chord, cadence_key)
            chord_type = rn.figure.replace('7', '').replace('6', '')
            
            # Secondary Dominant Check: V/V -> V
            is_v_of_v = False
            if i > 0 and len(measures[i-1].flat.notes) > 0:
                prev_chord = measures[i-1].flat.notes[-1]
                if isinstance(prev_chord, chord.Chord):
                    # Simple check: Is previous chord a Major triad on the 2nd degree?
                    prev_rn = romanNumeralFromChord(prev_chord, cadence_key)
                    if prev_rn.figure.startswith('II') or prev_rn.figure.startswith('V/V'):
                        if chord_type in ['V', 'v']:
                            is_v_of_v = True

            # Split Logic:
            # 1. Must have passed min_measures
            # 2. Must hit a harmonic arrival (I/V) OR a fermata
            
            has_fermata = len(m.flat.getElementsByClass(Fermata)) > 0
            is_long = last_chord.quarterLength >= 2.0
            is_harmonic_arrival = chord_type in ['I', 'V', 'i', 'v'] or is_v_of_v
            
            should_split = False
            if measures_since_split >= min_measures:
                if has_fermata:
                    should_split = True
                elif is_harmonic_arrival and is_long:
                    should_split = True
                elif measures_since_split >= (min_measures + 2) and is_harmonic_arrival:
                    # Don't let phrases get TOO long without an arrival
                    should_split = True

            if should_split:
                fermata_measures.append(m.number)
                last_split_m = m.number

        self.stdout.write(self.style.SUCCESS(f"Detected {len(fermata_measures)} phrases based on cadences."))

        # 3. Slicing and Creation
        start_m = measures[0].number
        for idx, end_m in enumerate(fermata_measures):
            self.stdout.write(f"Phrase {idx+1}: Measures {start_m} to {end_m}")
            
            if dry_run:
                start_m = end_m + 1
                continue

            # Extract measure range
            # Note: music21.measures(start, end) is inclusive but also returns
            # the following measure for tie/slur resolution. Remove any measures
            # with number > end_m to avoid leaking the pickup to the next phrase.
            phrase_score = score.measures(start_m, end_m)
            for part in phrase_score.parts:
                # Remove trailing overflow measures (music21 includes one extra for tie resolution)
                for m in list(part.getElementsByClass(stream.Measure)):
                    if m.number > end_m:
                        part.remove(m)
                # Remove first-ending duplicates: when a chorale has repeat brackets,
                # music21 stores both endings with the same measure number.
                # Keep only the last occurrence (second ending = cadential measure).
                seen_nums = {}
                for m in list(part.getElementsByClass(stream.Measure)):
                    if m.number in seen_nums:
                        part.remove(seen_nums[m.number])  # remove earlier occurrence
                    seen_nums[m.number] = m

            # GAP FILTER: Skip phrases with silent or rest-dominated measures.
            # music21 uses implicit rests (no Rest objects), so we compare
            # filled duration (notes_ql) against the full bar duration.
            # Anacrusis (pickup) measures are exempted — see _phrase_has_silent_measure.
            if _phrase_has_silent_measure(phrase_score):
                self.stdout.write(self.style.WARNING(f"  Skipping Phrase {idx+1} (mm. {start_m}-{end_m}): Contains silent/rest-heavy measures (Gap Filter)."))
                start_m = end_m + 1
                continue
            
            # 3. Detect Key and Mode
            try:
                # FORCE GLOBAL KEY FOR ALL PHRASES (per-phrase detection unreliable for short phrases)
                m21_key = score_key

                # Build HarmonyLab key format: "iA_", "jC_", "iD_", "jBb", "jF#" etc.
                tonic = m21_key.tonic.name  # e.g. "A", "B-", "F#"
                if "-" in tonic:
                    hl_tonic = tonic[0] + "b"   # "B-" → "Bb"
                elif "#" in tonic:
                    hl_tonic = tonic             # "F#" → "F#"
                else:
                    hl_tonic = tonic + "_"       # "A" → "A_"
                mode_prefix = "j" if m21_key.mode == "major" else "i"
                harmony_key = mode_prefix + hl_tonic   # e.g. "iA_", "jC_"

                # Build sharps/flats string for staff key signature ("", "#", "b", "##", etc.)
                sharps = m21_key.sharps
                harmony_sig = "#" * sharps if sharps > 0 else "b" * abs(sharps)
            except Exception:
                harmony_sig = ""      # no accidentals (C major / A minor)
                harmony_key = "jC_"  # default to C major

            try:
                detected_skills, detected_complexity = analyze_chunk_skills(phrase_score, m21_key.tonicPitchNameWithCase)
                detected_complexity = max(1, min(12, detected_complexity))
                playlist_complexity = max(1, min(10, detected_complexity))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Skills analysis failed: {e}"))
                detected_skills, detected_complexity, playlist_complexity = [], 1, 1

            # Convert to CIR JSON
            cir_data = m21_to_cir(phrase_score, key_override=harmony_key)
            
            # 4. Map to UMTO Interaction Mode
            # `roman` and `figures` are label-entry exercises (show prompts/slots),
            # while `matching` is the inverse mode (label shown, play the pitch).
            if mode in ('play', 'play_figures'):
                umto_mode = InteractionMode.PLAYBACK
            elif mode == 'matching':
                umto_mode = InteractionMode.ANALYSIS_MATCH
            else:
                umto_mode = InteractionMode.IDENTIFICATION
            
            # 5. Build Intro Text
            if mode == 'figures':
                intro_text = f"Provide the Figured Bass for this phrase from Bach (BWV {bwv_display}, mm. {start_m}-{end_m})."
            elif mode == 'matching' or mode == 'roman':
                intro_text = f"Analyze the Roman Numerals for this phrase from Bach (BWV {bwv_display}, mm. {start_m}-{end_m})."
            else:
                intro_text = f"Play all four voices of this Bach phrase (BWV {bwv_display}, mm. {start_m}-{end_m})."

            description = f"Bach {bwv_display} - Phrase {idx+1} (mm.{start_m}-{end_m}) [{mode}]"

            if _description_exists(description[:60], authored_by=author) and not overwrite:
                self.stdout.write(self.style.WARNING(f"  Skipping (exists): {description[:60]}"))
                start_m = end_m + 1
                continue

            # Extract unit number from extra_tags for analysis tagging
            unit_nums = []
            for tag in options['extra_tags']:
                m2 = re.match(r'^unit:(\d+)$', tag)
                if m2:
                    unit_nums.append(int(m2.group(1)))

            # Build analysis overrides based on mode
            analysis_overrides = None
            if mode in ('roman', 'matching', 'play', 'play_figures'):
                analysis_overrides = _build_roman_analysis_overrides(
                    phrase_score, m21_key, unit_nums, riem_num
                )
                self.stdout.write(f"  Built {len(analysis_overrides)} WiR analysis slices")
            elif mode in ('figures', 'figures_unabbreviated'):
                try:
                    analysis_overrides = _build_figured_bass_overrides(
                        phrase_score, m21_key
                    )
                    self.stdout.write(f"  Built {len(analysis_overrides)} figured bass slices")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Figured bass overrides failed: {e}"))

            display = None
            if mode == 'figures':
                analysis_type = 'figured_bass'
            elif mode == 'figures_unabbreviated':
                analysis_type = 'figured_bass_unabbreviated'
            elif mode == 'play_figures':
                analysis_type = 'figured_bass'
                display = {
                    "showFigures": True,
                    "figureStyle": "figures_abbrev",
                    "analysisRenderer": "notater",
                }
            else:
                analysis_type = 'roman'

            umto_kwargs = dict(
                exercise_id="TEMP",
                source=intro_text,
                key=harmony_key,
                meter=cir_data.get("meta", {}).get("time", "4/4"),
                clef="keyboard",
                complexity_score=detected_complexity,
                mode=umto_mode,
                analysis_type=analysis_type,
            )
            if analysis_overrides is not None:
                umto_kwargs["analysis_overrides"] = analysis_overrides
            if display is not None:
                umto_kwargs["display"] = display

            # Create the Exercise via UMTO factory
            ex = save_umto_exercise(
                description=description[:60],
                score_data=cir_data,
                author=author,
                skill_tags=list(set(detected_skills + options['extra_tags'])),
                complexity=playlist_complexity,
                is_public=options['public'],
                umto_kwargs=umto_kwargs,
                overwrite=overwrite,
            )
            self.stdout.write(self.style.SUCCESS(f"  Created UMTO Exercise {ex.id}"))

            # Update start for next phrase
            start_m = end_m + 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully imported {len(fermata_measures)} phrases as exercises."))
