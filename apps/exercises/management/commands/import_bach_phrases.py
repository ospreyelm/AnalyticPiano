import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

import music21
from music21.expressions import Fermata

from apps.exercises.models import Exercise
from apps.exercises.utils.m21_cir_converter import m21_to_cir
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills

class Command(BaseCommand):
    help = 'Import a Bach chorale and split it into phrases based on fermatas.'

    def add_arguments(self, parser):
        parser.add_argument('--bwv', type=str, required=True, help='BWV number (e.g. 1, 363, bwv1)')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--mode', type=str, choices=['play', 'roman', 'figures', 'matching'], default='play', help='Exercise mode')
        parser.add_argument('--min-measures', type=int, default=3, help='Minimum measures per phrase')
        parser.add_argument('--dry-run', action='store_true', help='Show phrase ranges without creating exercises')

    def handle(self, *args, **options):
        bwv_input = options['bwv'].lower()
        author_email = options['author']
        mode = options['mode']
        min_measures = options['min_measures']
        dry_run = options['dry_run']

        # Clean BWV string
        bwv_num = bwv_input.replace('bwv', '').strip()
        try:
            bwv_int = int(bwv_num)
        except ValueError:
            raise CommandError(f"Invalid BWV number: {bwv_input}")

        # 1. Validate Author
        User = get_user_model()
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        self.stdout.write(f"Searching for BWV {bwv_int} in music21 corpus...")
        score = None
        
        # Try direct path variations
        for path_fmt in [f'bach/bwv{bwv_int}', f'bach/bwv{bwv_int:03d}']:
            try:
                score = music21.corpus.parse(path_fmt)
                self.stdout.write(f"  Found via path: {path_fmt}")
                break
            except:
                continue

        # Try search if path fails
        if not score:
            self.stdout.write(f"  Path lookup failed, trying corpus search...")
            search_results = music21.corpus.search(f'bwv{bwv_int}', 'bach')
            if not search_results:
                search_results = music21.corpus.search(f'bwv{bwv_int}')
            
            if search_results:
                score = search_results[0].parse()
                self.stdout.write(f"  Found via search: {search_results[0]}")
            else:
                raise CommandError(f"Could not find BWV {bwv_int} in the music21 corpus.")

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
            if not isinstance(last_chord, music21.chord.Chord):
                continue

            # How long since the last split?
            measures_since_split = m.number - last_split_m
            
            # Harmonic Check
            from music21.roman import romanNumeralFromChord
            rn = romanNumeralFromChord(last_chord, global_key)
            chord_type = rn.figure.replace('7', '').replace('6', '')
            
            # Secondary Dominant Check: V/V -> V
            is_v_of_v = False
            if i > 0:
                prev_chord = measures[i-1].flat.notes[-1]
                if isinstance(prev_chord, music21.chord.Chord):
                    # Simple check: Is previous chord a Major triad on the 2nd degree?
                    prev_rn = romanNumeralFromChord(prev_chord, global_key)
                    if prev_rn.figure.startswith('II') or prev_rn.figure.startswith('V/V'):
                        if chord_type in ['V', 'v']:
                            is_v_of_v = True

            # Refined Slicing Rule:
            # 1. Standard Fermata/Long arrival (Always split)
            # 2. Intermediate Arrival: I or V if at least 2 bars have passed
            is_long = last_chord.quarterLength >= 2.0
            is_harmonic_arrival = chord_type in ['I', 'V', 'i', 'v'] or is_v_of_v
            
            should_split = False
            if is_long and is_harmonic_arrival:
                should_split = True
            elif measures_since_split >= min_measures and is_harmonic_arrival:
                # Prioritize splitting at the min_measures threshold if we hit a cadence
                should_split = True

            if should_split:
                fermata_measures.append(m.number)
                last_split_m = m.number
            
            # Explicit Fermata Check (Safety)
            elif len(m.flat.getElementsByClass(music21.expressions.Fermata)) > 0:
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
            # Note: music21.measures(start, end) is inclusive
            phrase_score = score.measures(start_m, end_m)
            
            # Analyze skills for this phrase
            try:
                # Key analysis for the whole piece or just the phrase? 
                # Better to analyze the chunk key for modulation awareness
                chunk_key = phrase_score.analyze('key').tonicPitchNameWithCase
            except:
                chunk_key = "C"

            try:
                detected_skills, detected_complexity = analyze_chunk_skills(phrase_score, chunk_key)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Skills analysis failed: {e}"))
                detected_skills, detected_complexity = [], 1

            # Convert to CIR JSON
            cir_data = m21_to_cir(phrase_score)
            
            if mode in ['roman', 'figures', 'matching']:
                analysis_type = "roman"
                if mode == 'figures':
                    analysis_type = "figured_bass"
                
                intro_text = f"Provide a Roman Numeral analysis for this phrase from BWV {bwv_num} (mm. {start_m}-{end_m})."
                if mode == 'figures':
                    intro_text = f"Provide the Figured Bass for this phrase from BWV {bwv_num} (mm. {start_m}-{end_m})."
                elif mode == 'matching':
                    intro_text = f"Match the Roman Numerals to the notes in this phrase from BWV {bwv_num} (mm. {start_m}-{end_m})."

                exercise_data = {
                    "key": chunk_key,
                    "type": "chorale_identification",
                    "analysisType": analysis_type,
                    "score": cir_data,
                    "source": {
                        "type": "bach_corpus",
                        "bwv": bwv_num,
                        "phrase": idx + 1,
                        "measures": f"{start_m}-{end_m}"
                    },
                    "display": {
                        "showFigures": False,
                        "showRomans": False,
                        "transpose": 0,
                        "tempo": 60
                    },
                    "introText": intro_text,
                    "staffDistribution": "keyboard"
                }
            else:
                exercise_data = {
                    "key": chunk_key,
                    "type": "chorale",
                    "mode": "play-all-voices",
                    "score": cir_data,
                    "source": {
                        "type": "bach_corpus",
                        "bwv": bwv_num,
                        "phrase": idx + 1,
                        "measures": f"{start_m}-{end_m}"
                    },
                    "display": {
                        "showFigures": False,
                        "showRomans": False,
                        "transpose": 0,
                        "tempo": 60
                    },
                    "introText": f"Analyze the following phrase from BWV {bwv_num} (mm. {start_m}-{end_m}).",
                    "staffDistribution": "keyboard"
                }

            description = f"Bach BWV {bwv_num} - Phrase {idx+1} (mm.{start_m}-{end_m})"
            
            ex = Exercise(
                description=description[:60], # Max length
                data=exercise_data,
                authored_by=author,
                is_public=False,
                tags=['bach'],
                skill_tags=detected_skills,
                complexity=detected_complexity
            )
            ex.save()
            self.stdout.write(self.style.SUCCESS(f"  Created Exercise {ex.id}"))

            # Update start for next phrase
            start_m = end_m + 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully imported {len(fermata_measures)} phrases as exercises."))
