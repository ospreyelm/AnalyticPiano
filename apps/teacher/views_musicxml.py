import json
import logging
import os
import sys
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.teacher.decorators import teacher_required

# Add scripts directory to path to import fetch_bach_chorales
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts'))
try:
    from fetch_bach_chorales import m21_to_cir
except ImportError:
    m21_to_cir = None

from apps.exercises.umto import InteractionMode
from apps.exercises.models import Playlist
from apps.exercises.umto_factory import build_umto_payload, save_chordal_umto_exercise, save_umto_exercise
from apps.exercises.utils.umto_import_router import classify_musicxml_score
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills
from apps.exercises.utils.teacher_play_modes import resolve_mode
from apps.exercises.management.commands.import_musicxml import _build_import_payload_for_score

logger = logging.getLogger(__name__)
User = get_user_model()


@teacher_required
@require_POST
def import_musicxml_preview_view(request):
    """
    POST: parses an uploaded MusicXML file and returns a preview JSON payload
    compatible with the Vexflow rendering path, along with auto-detected key/skills.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Permission denied."}, status=403)

    musicxml_file = request.FILES.get("musicxml_file")
    if not musicxml_file:
        return JsonResponse({"error": "No musicxml_file uploaded."}, status=400)

    try:
        start_measure = int(request.POST.get("start", 0))
    except (TypeError, ValueError):
        start_measure = 0

    try:
        end_val = request.POST.get("end")
        end_measure = int(end_val) if end_val and end_val.strip() else None
    except (TypeError, ValueError):
        end_measure = None

    harmony_key = request.POST.get("harmony_key") or ""
    try:
        complexity_val = request.POST.get("complexity")
        complexity = int(complexity_val) if complexity_val else None
    except (TypeError, ValueError):
        complexity = None

    # Write to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        for chunk in musicxml_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        from music21 import converter
        score = converter.parse(tmp_path)

        # Detect Key if not provided
        if not harmony_key:
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

        # Run skills analyzer
        try:
            detected_tags, detected_complexity = analyze_chunk_skills(score, harmony_key)
        except Exception as e:
            logger.warning(f"analyze_chunk_skills failed: {e}")
            detected_tags, detected_complexity = set(), 1

        if complexity is None:
            complexity = detected_complexity

        # Classify route
        decision = classify_musicxml_score(score)

        basename = os.path.basename(musicxml_file.name)
        title = os.path.splitext(basename)[0]

        # Build payload
        import_payload = _build_import_payload_for_score(
            score,
            title=title,
            harmony_key=harmony_key,
            start_measure=start_measure,
            end_measure=end_measure,
            complexity=complexity,
        )

        if decision.route == "chordal":
            frontend_payload = import_payload.payload
        else:
            if not m21_to_cir:
                raise ImportError("m21_to_cir helper not found in scripts/fetch_bach_chorales.py")
            frontend_payload = build_umto_payload(
                score_data=import_payload.score_data,
                exercise_id="TEMP",
                source=f"Play {title}.",
                key=harmony_key,
                meter=import_payload.meter,
                clef=import_payload.score_data.get("meta", {}).get("clef", "treble"),
                complexity_score=complexity,
                mode=InteractionMode.PLAYBACK,
            )

        # Suggest units
        suggested_units = []
        if detected_tags:
            try:
                from apps.exercises.services.unit_suggester import suggest_units_from_tags
                suggested_units = suggest_units_from_tags(list(detected_tags), top_n=5)
            except Exception:
                pass

        # Cleanup
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        return JsonResponse({
            "success": True,
            "route": decision.route,
            "key": harmony_key,
            "complexity": complexity,
            "detected_skills": list(detected_tags),
            "suggested_units": suggested_units,
            "title": title,
            "payload": frontend_payload,
        })

    except Exception as e:
        logger.error(f"Error parsing MusicXML preview: {e}", exc_info=True)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return JsonResponse({"error": str(e)}, status=400)


@teacher_required
@require_POST
def import_musicxml_save_view(request):
    """
    POST: parses the uploaded MusicXML file using the specified ranges/options,
    saves the base UMTO exercise, and appends it to the canonical teacher-play
    playlist for (author, unit, mode). No playlist picker or multi-mode fan-out.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Permission denied."}, status=403)

    musicxml_file = request.FILES.get("musicxml_file")
    if not musicxml_file:
        return JsonResponse({"error": "No musicxml_file uploaded."}, status=400)

    description = request.POST.get("description", "").strip()
    if not description or len(description) > 60:
        return JsonResponse({"error": "description must be 60 characters or fewer."}, status=400)

    # Reject explicit playlist routing
    if request.POST.get("playlist_id") or request.POST.get("playlist_name"):
        return JsonResponse(
            {"error": "Playlist destination is automatic for teacher-play saves. "
                      "Do not send playlist_id or playlist_name."},
            status=400,
        )

    # Single unit
    unit_tags = request.POST.getlist("unit") or []
    if len(unit_tags) == 1 and "," in unit_tags[0]:
        unit_tags = [u.strip() for u in unit_tags[0].split(",") if u.strip()]
    unit_tags = [u for u in unit_tags if u]
    if len(unit_tags) != 1:
        return JsonResponse({"error": "Exactly one unit must be selected."}, status=400)

    try:
        unit = int(unit_tags[0])
    except ValueError:
        return JsonResponse({"error": "Unit must be an integer."}, status=400)

    skill_tags = [f"unit:{unit}"]
    free_tags = request.POST.get("tags") or ""
    if free_tags:
        for t in free_tags.split(","):
            cleaned_t = t.strip()
            if cleaned_t:
                skill_tags.append(cleaned_t)

    # Single mode
    from apps.exercises.utils.playlist_naming import SUPPORTED_TEACHER_PLAY_MODES
    modes = request.POST.getlist("modes")
    if modes:
        if len(modes) != 1:
            return JsonResponse(
                {"error": "Exactly one mode is required. Send mode not modes (multiple)."},
                status=400,
            )
        mode = modes[0]
    else:
        mode = request.POST.get("mode", "play")

    if mode not in SUPPORTED_TEACHER_PLAY_MODES:
        return JsonResponse({"error": f"Unsupported interaction mode: {mode}"}, status=400)

    is_public = request.POST.get("is_public") in ("true", "on", "1")
    save_as_official = request.POST.get("save_as_official") in ("true", "on", "1")

    if save_as_official and not request.user.is_superuser:
        return JsonResponse({"error": "Only superusers can save official exercises."}, status=403)

    if save_as_official:
        factory_email = getattr(settings, "FACTORY_USER_EMAIL", None)
        author = User.objects.filter(email=factory_email).first()
        if not author:
            return JsonResponse({"error": f"Factory user {factory_email} does not exist."}, status=400)
    else:
        author = request.user

    try:
        start_measure = int(request.POST.get("start", 0))
    except (TypeError, ValueError):
        start_measure = 0

    try:
        end_val = request.POST.get("end")
        end_measure = int(end_val) if end_val and end_val.strip() else None
    except (TypeError, ValueError):
        end_measure = None

    harmony_key = request.POST.get("harmony_key") or "jC_"

    try:
        complexity = int(request.POST.get("complexity", 1))
    except (TypeError, ValueError):
        complexity = 1

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        for chunk in musicxml_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        from music21 import converter
        score = converter.parse(tmp_path)

        decision = classify_musicxml_score(score)

        import_payload = _build_import_payload_for_score(
            score,
            title=description,
            harmony_key=harmony_key,
            start_measure=start_measure,
            end_measure=end_measure,
            complexity=complexity,
        )

        from django.db import transaction
        from apps.exercises.services.canonical_playlist import (
            append_exercise_to_canonical_playlist,
            resolve_canonical_playlist,
        )

        with transaction.atomic():
            resolved = resolve_mode(mode)
            interaction_mode = resolved["interaction_mode"]
            analysis_type = resolved["analysis_type"]

            if decision.route == "chordal":
                mode_display = {
                    "showRomans": False,
                    "showFigures": False,
                    "showChordLabels": False,
                    "showScaleDegrees": False,
                    "showNoteNames": False,
                }
                if resolved["display"]:
                    mode_display.update(resolved["display"])

                exercise = save_chordal_umto_exercise(
                    description=description,
                    author=author,
                    chords=import_payload.chords,
                    key=harmony_key,
                    meter=import_payload.meter,
                    clef="keyboard",
                    staff_distribution="keyboard",
                    skill_tags=skill_tags,
                    complexity=complexity,
                    is_public=is_public,
                    auto_playlist=False,
                    barline_offsets=import_payload.barline_offsets,
                    analysis=import_payload.analysis,
                    display=mode_display,
                    mode=interaction_mode,
                    analysis_type=analysis_type,
                )
                if save_as_official:
                    exercise.is_official = True
                    exercise.save(update_fields=["is_official"])
            else:
                umto_kwargs = dict(
                    exercise_id="TEMP",
                    source=f"Play {description}.",
                    key=harmony_key,
                    meter=import_payload.meter,
                    clef=import_payload.score_data.get("meta", {}).get("clef", "treble"),
                    complexity_score=complexity,
                    mode=interaction_mode,
                    analysis_type=analysis_type,
                )
                import copy
                score_data_copy = copy.deepcopy(import_payload.score_data)
                exercise = save_umto_exercise(
                    description=description,
                    score_data=score_data_copy,
                    author=author,
                    skill_tags=skill_tags,
                    complexity=complexity,
                    is_public=is_public,
                    umto_kwargs=umto_kwargs,
                    auto_playlist=False,
                )
                if save_as_official:
                    exercise.is_official = True
                    exercise.save(update_fields=["is_official"])

            playlist = resolve_canonical_playlist(
                author=author,
                unit=unit,
                mode=mode,
                is_public=is_public,
                is_official=save_as_official,
            )
            append_exercise_to_canonical_playlist(playlist, exercise)

            # Create transpositions if requested
            create_transpositions = request.POST.get("create_transpositions") in ("true", "on", "1")
            key_set_str = request.POST.get("key_set") or ""
            key_set = [k.strip() for k in key_set_str.split(",") if k.strip()]

            if create_transpositions and key_set:
                from apps.exercises.services.transposition_service import generate_transposed_copies
                generate_transposed_copies(
                    source_exercise=exercise,
                    key_set=key_set,
                    playlist=playlist,
                    author=author,
                    is_official=save_as_official,
                    overwrite=False,
                )

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        return JsonResponse({
            "success": True,
            "id": exercise.id,
            "ids": [exercise.id],
            "reviewStatus": (exercise.data or {}).get("score", {}).get("umto", {}).get(
                "metadata", {}
            ).get("analysis_review_status", "none"),
            "playlistId": playlist.id,
            "playlistName": playlist.name,
            "playlists": [{"id": playlist.id, "name": playlist.name, "mode": mode}],
        }, status=201)

    except Exception as e:
        logger.error(f"Error saving MusicXML: {e}", exc_info=True)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return JsonResponse({"error": str(e)}, status=400)
