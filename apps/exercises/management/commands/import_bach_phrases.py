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


def _build_roman_analysis_overrides(phrase_score, global_key, unit_tags: list) -> list:
    """Analyze a phrase and return UMTO analysis_overrides with raw Roman numerals.

    Stores the raw music21 figure in raw_roman_numeral. Targeting (curriculum
    filtering) happens at request time in generate_exercise_context; nothing is
    filtered here.
    """
    from music21.roman import romanNumeralFromChord

    chorded = phrase_score.chordify()
    measures = list(chorded.getElementsByClass('Measure'))
    if not measures:
        return []

    first_measure_offset = measures[0].offset
    overrides = []
    seen_offsets = set()

    for m in measures:
        measure_start = m.offset - first_measure_offset
        for element in m.flat.notes:
            if not isinstance(element, chord.Chord):
                continue
            abs_offset = round(measure_start + float(element.offset), 5)
            if abs_offset in seen_offsets:
                continue
            seen_offsets.add(abs_offset)
            try:
                rn = romanNumeralFromChord(element, global_key)
                figure = rn.figure
            except Exception:
                figure = None

            overrides.append({
                "offset": abs_offset,
                "content": {
                    "roman_numeral": None, # targeting happens at request time
                    "raw_roman_numeral": figure,
                    "figured_bass": None,
                    "pop_symbol": None,
                    "functional_label": None,
                },
                "unit_tags": list(unit_tags),
            })

    return overrides


class Command(BaseCommand):
    help = 'Import a Bach chorale and split it into phrases based on fermatas.'

    def add_arguments(self, parser):
        parser.add_argument('--bwv', type=int, help='BWV number (e.g. 1)')
        parser.add_argument('--movement', type=int, help='Movement number (e.g. 6)')
        parser.add_argument('--riemenschneider', type=int, help='Riemenschneider number (e.g. 1-371)')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--mode', type=str, choices=['play', 'roman', 'figures', 'matching'], default='play', help='Exercise mode')
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
            global_key = score.analyze('key')
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
            rn = romanNumeralFromChord(last_chord, global_key)
            chord_type = rn.figure.replace('7', '').replace('6', '')
            
            # Secondary Dominant Check: V/V -> V
            is_v_of_v = False
            if i > 0 and len(measures[i-1].flat.notes) > 0:
                prev_chord = measures[i-1].flat.notes[-1]
                if isinstance(prev_chord, chord.Chord):
                    # Simple check: Is previous chord a Major triad on the 2nd degree?
                    prev_rn = romanNumeralFromChord(prev_chord, global_key)
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
            has_silent_measure = False
            for m_test in phrase_score.parts[0].getElementsByClass(stream.Measure):
                notes_ql = sum(n.quarterLength for n in m_test.flatten().notes)
                bar_ql = m_test.barDuration.quarterLength
                # Skip if less than half the measure is filled with notes
                if bar_ql > 0 and notes_ql < bar_ql * 0.5:
                    has_silent_measure = True
                    break

            if has_silent_measure:
                self.stdout.write(self.style.WARNING(f"  Skipping Phrase {idx+1} (mm. {start_m}-{end_m}): Contains silent/rest-heavy measures (Gap Filter)."))
                start_m = end_m + 1
                continue
            
            # 3. Detect Key and Mode
            try:
                # FORCE GLOBAL KEY FOR ALL PHRASES (per-phrase detection unreliable for short phrases)
                m21_key = global_key

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
            if mode == 'play':
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

            # Build roman numeral analysis for label-entry modes
            analysis_overrides = None
            if mode in ('roman', 'figures', 'matching'):
                try:
                    analysis_overrides = _build_roman_analysis_overrides(
                        phrase_score, m21_key, unit_nums
                    )
                    self.stdout.write(f"  Built {len(analysis_overrides)} analysis slices")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Analysis overrides failed: {e}"))

            umto_kwargs = dict(
                exercise_id="TEMP",
                source=intro_text,
                key=harmony_key,
                meter=cir_data.get("meta", {}).get("time", "4/4"),
                clef="keyboard",
                complexity_score=detected_complexity,
                mode=umto_mode,
            )
            if analysis_overrides is not None:
                umto_kwargs["analysis_overrides"] = analysis_overrides

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
