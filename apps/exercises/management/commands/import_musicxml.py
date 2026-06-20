import json
import os
import glob
from dataclasses import dataclass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

# Import analysis and conversion utilities
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../scripts'))
try:
    from fetch_bach_chorales import m21_to_cir, build_events
except ImportError:
    m21_to_cir = None
    build_events = None

from apps.exercises.umto import InteractionMode
from apps.exercises.models import Exercise
from apps.exercises.umto_factory import build_chordal_umto_payload, save_umto_exercise
from apps.exercises.utils.umto_import_router import (
    MusicXMLRouteDecision,
    build_chordal_analysis_slices,
    classify_musicxml_score,
    musicxml_score_to_chord_events,
)
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills

User = get_user_model()


@dataclass(frozen=True)
class ImportMusicXMLPayload:
    decision: MusicXMLRouteDecision
    score_data: dict | None
    payload: dict | None
    meter: str
    chords: list[dict] | None = None
    analysis: list[dict] | None = None
    barline_offsets: list[float] | None = None


def _score_meter(score) -> str:
    from music21 import meter

    ts = score.recurse().getElementsByClass(meter.TimeSignature).first()
    return str(ts.ratioString) if ts else "4/4"


def _meter_quarter_length(meter_text: str) -> float:
    try:
        numerator, denominator = meter_text.split("/", 1)
        return int(numerator) * (4.0 / int(denominator))
    except (AttributeError, ValueError, ZeroDivisionError):
        return 4.0


def _suggest_barline_offsets(chords: list[dict], meter_text: str) -> list[float]:
    """Derive bar-boundary offsets from chord onsets and the meter, mirroring the
    manual editor's ChordalBarlinesLogic.suggestBarlines (lab/static/js/src/utils/
    chordal_barlines_logic.js). MusicXML-sourced chords are metrically aligned to
    the original score's real barlines, so every meter-length multiple that
    coincides with a chord onset is a real bar boundary.
    """
    if not chords:
        return []
    bar_len = _meter_quarter_length(meter_text)
    if not bar_len:
        return []
    onsets = {round(float(c["offset"]), 6) for c in chords}
    total = round(
        max(float(c["offset"]) + float(c["duration"]) for c in chords), 6
    )
    offsets = []
    boundary = round(bar_len, 6)
    while boundary < total - 1e-6:
        if boundary in onsets:
            offsets.append(boundary)
        boundary = round(boundary + bar_len, 6)
    return offsets


def _excerpt_chord_events(chords: list[dict], *, meter_text: str,
                          start_measure: int, end_measure: int | None) -> list[dict]:
    measure_ql = _meter_quarter_length(meter_text)
    start_offset = start_measure * measure_ql
    end_offset = end_measure * measure_ql if end_measure is not None else None
    excerpt = []
    for chord_event in chords:
        offset = float(chord_event.get("offset", 0.0))
        if offset < start_offset:
            continue
        if end_offset is not None and offset >= end_offset:
            continue
        copied = dict(chord_event)
        copied["offset"] = round(offset - start_offset, 6)
        excerpt.append(copied)
    return excerpt


def _build_import_payload_for_score(
    score,
    *,
    title: str,
    harmony_key: str,
    start_measure: int,
    end_measure: int | None,
    complexity: int,
) -> ImportMusicXMLPayload:
    decision = classify_musicxml_score(score)
    meter = _score_meter(score)

    if decision.route == "chordal":
        chords = _excerpt_chord_events(
            musicxml_score_to_chord_events(score),
            meter_text=meter,
            start_measure=start_measure,
            end_measure=end_measure,
        )
        analysis = build_chordal_analysis_slices(chords, harmony_key=harmony_key)
        barline_offsets = _suggest_barline_offsets(chords, meter)
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source=f"Play {title}.",
            key=harmony_key,
            meter=meter,
            clef="keyboard",
            complexity_score=complexity,
            mode=InteractionMode.PLAYBACK,
            chords=chords,
            analysis=analysis,
            analysis_review_status="generated" if analysis else "none",
            barline_offsets=barline_offsets,
        )
        return ImportMusicXMLPayload(
            decision=decision,
            score_data=None,
            payload=payload,
            meter=meter,
            chords=chords,
            analysis=analysis,
            barline_offsets=barline_offsets,
        )

    cir = m21_to_cir(score, key_override=harmony_key)
    meta = cir.get('meta', {})
    measures = cir.get('measures', [])
    excerpt_measures = measures[start_measure:end_measure] if end_measure else measures[start_measure:]
    score_data = {"meta": meta, "measures": excerpt_measures}
    return ImportMusicXMLPayload(
        decision=decision,
        score_data=score_data,
        payload=None,
        meter=meta.get("time", meter),
    )


class Command(BaseCommand):
    help = 'Import MusicXML files/directories as Exercises using music21 → CIR pipeline with Auto-Tagging'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='Path to MusicXML file or directory')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--public', action='store_true', help='Make the exercises public')
        parser.add_argument('--start', type=int, default=0, help='Start measure (0-indexed, default: 0)')
        parser.add_argument('--end', type=int, default=None, help='End measure (exclusive, default: all)')

    def handle(self, *args, **options):
        path = options['path']
        author_email = options['author']
        is_public = options['public']

        # Check dependencies
        if m21_to_cir is None or build_events is None:
            raise CommandError('Could not import converter functions. Ensure scripts/fetch_bach_chorales.py exists.')

        # Find the author
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        # Determine file list
        if os.path.isfile(path):
            files = [path]
        elif os.path.isdir(path):
            files = []
            for ext in ('*.xml', '*.musicxml', '*.mxl'):
                files.extend(glob.glob(os.path.join(path, '**', ext), recursive=True))
        else:
            raise CommandError(f'Path not found: {path}')

        if not files:
            self.stdout.write(self.style.WARNING(f'No MusicXML files found in {path}'))
            return

        self.stdout.write(f'Integrating {len(files)} files into Knowledge Graph...')
        
        success_count = 0
        for f in files:
            try:
                exercise = self.process_file(f, author, is_public, options)
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f'  [SUCCESS] {os.path.basename(f)} -> ID: {exercise.id}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  [FAILED] {os.path.basename(f)}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\nBulk Ingestion Complete: {success_count}/{len(files)} exercises imported.'))

    def process_file(self, file_path, author, is_public, options):
        from music21 import converter
        
        start_measure = options['start']
        end_measure = options['end']

        # Load MusicXML
        score = converter.parse(file_path)

        # Detect Key
        try:
            m21_key = score.analyze('key')
            tonic = m21_key.tonic.name
            if "-" in tonic:
                hl_tonic = tonic[0] + "b"
            elif "#" in tonic:
                hl_tonic = tonic
            else:
                hl_tonic = tonic + "_"
            mode_prefix = "j" if m21_key.mode == "major" else "i"
            harmony_key = mode_prefix + hl_tonic
        except Exception:
            harmony_key = "jC_"

        basename = os.path.basename(file_path)
        title = os.path.splitext(basename)[0]

        # AUTO-ANALysis for Knowledge Graph
        # We analyze the score to get Unit tags and complexity
        detected_tags, complexity = analyze_chunk_skills(score, harmony_key)

        import_payload = _build_import_payload_for_score(
            score,
            title=title,
            harmony_key=harmony_key,
            start_measure=start_measure,
            end_measure=end_measure,
            complexity=complexity,
        )

        if import_payload.decision.route == "chordal":
            payload = import_payload.payload
            exercise = Exercise(
                description=title,
                data=payload,
                authored_by=author,
                skill_tags=list(detected_tags),
                complexity=complexity,
                is_public=is_public,
                time_signature=import_payload.meter,
            )
            exercise.save()
            exercise.data["score"]["umto"]["metadata"]["exercise_id"] = exercise.id
            exercise.save(update_fields=["data"])
            return exercise

        if not import_payload.score_data or not import_payload.score_data.get("measures"):
            raise Exception('No measures found')
        
        exercise = save_umto_exercise(
            description=title,
            score_data=import_payload.score_data,
            author=author,
            skill_tags=list(detected_tags),
            complexity=complexity,
            is_public=is_public,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source=f"Play {title}.",
                key=harmony_key,
                meter=import_payload.meter,
                clef=import_payload.score_data.get("meta", {}).get("clef", "treble"),
                complexity_score=complexity,
                mode=InteractionMode.PLAYBACK,
            )
        )

        return exercise
