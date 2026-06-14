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
from apps.exercises.models import Exercise, Playlist
from apps.exercises.umto_factory import build_umto_payload, save_umto_exercise
from apps.exercises.utils.umto_import_router import classify_musicxml_score
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills
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
    saves the base UMTO exercise, links it to the target playlist, and generates transpositions if requested.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Permission denied."}, status=403)

    musicxml_file = request.FILES.get("musicxml_file")
    if not musicxml_file:
        return JsonResponse({"error": "No musicxml_file uploaded."}, status=400)

    description = request.POST.get("description", "").strip()
    if not description or len(description) > 60:
        return JsonResponse({"error": "description must be 60 characters or fewer."}, status=400)

    unit_tags = request.POST.getlist("unit") or []
    if len(unit_tags) == 1 and "," in unit_tags[0]:
        unit_tags = [u.strip() for u in unit_tags[0].split(",") if u.strip()]

    skill_tags = []
    for u in unit_tags:
        if u:
            skill_tags.append(f"unit:{u}")

    free_tags = request.POST.get("tags") or ""
    if free_tags:
        for t in free_tags.split(","):
            cleaned_t = t.strip()
            if cleaned_t:
                skill_tags.append(cleaned_t)

    is_public = request.POST.get("is_public") in ("true", "on", True)
    save_as_official = request.POST.get("save_as_official") in ("true", "on", True)

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

    selected_modes = request.POST.getlist("modes") or [request.POST.get("mode", "play")]
    playlist_id = request.POST.get("playlist_id")
    playlist_name = request.POST.get("playlist_name")
    is_adaptive = request.POST.get("is_adaptive") in ("true", "on", True)

    if playlist_id:
        playlist_id = playlist_id.strip() or None
    if playlist_name:
        playlist_name = playlist_name.strip() or None

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

        effective_is_public = True if save_as_official else is_public

        from django.db import transaction
        from apps.exercises.models import ExercisePlaylistOrdered
        from django.db.models import Max

        created_exercises = []
        playlist = None

        with transaction.atomic():
            for mode in selected_modes:
                if decision.route == "chordal":
                    import copy
                    payload = copy.deepcopy(import_payload.payload)
                    display = {
                        "showRomans": mode == "roman",
                        "showFigures": mode == "figures",
                        "showChordLabels": False,
                        "showScaleDegrees": False,
                        "showNoteNames": False,
                    }
                    payload["display"] = display
                    payload["mode"] = mode
                    if "umto" in payload.get("score", {}):
                        payload["score"]["umto"]["metadata"]["mode"] = mode

                    exercise = Exercise(
                        description=description,
                        data=payload,
                        authored_by=author,
                        skill_tags=skill_tags,
                        complexity=complexity,
                        is_public=effective_is_public,
                        time_signature=import_payload.meter,
                    )
                    if save_as_official:
                        exercise.is_official = True
                    exercise.save()
                    exercise.data["score"]["umto"]["metadata"]["exercise_id"] = exercise.id
                    exercise.data["exerciseId"] = exercise.id
                    exercise.save(update_fields=["data"])
                else:
                    umto_mode = InteractionMode.IDENTIFICATION if mode == "identify" else InteractionMode.PLAYBACK
                    umto_kwargs = dict(
                        exercise_id="TEMP",
                        source=f"Play {description}.",
                        key=harmony_key,
                        meter=import_payload.meter,
                        clef=import_payload.score_data.get("meta", {}).get("clef", "treble"),
                        complexity_score=complexity,
                        mode=umto_mode,
                        analysis_type="figured_bass" if mode == "figures" else "roman",
                    )
                    import copy
                    score_data_copy = copy.deepcopy(import_payload.score_data)
                    exercise = save_umto_exercise(
                        description=description,
                        score_data=score_data_copy,
                        author=author,
                        skill_tags=skill_tags,
                        complexity=complexity,
                        is_public=effective_is_public,
                        umto_kwargs=umto_kwargs,
                        auto_playlist=False,
                    )
                    if save_as_official:
                        exercise.is_official = True
                        exercise.save(update_fields=["is_official"])

                created_exercises.append(exercise)

                # Target playlist mapping
                if playlist_id or playlist_name:
                    if playlist_id:
                        playlist = Playlist.objects.filter(id=playlist_id).first()
                        if not playlist:
                            raise ValueError("Playlist not found.")
                        if playlist.authored_by_id != author.id:
                            raise ValueError("Playlist must be authored by the save author.")
                    else:
                        playlist, pl_created = Playlist.objects.get_or_create(
                            name=playlist_name,
                            authored_by=author,
                            defaults={"is_public": effective_is_public, "is_adaptive": is_adaptive},
                        )

                    next_order = (
                        ExercisePlaylistOrdered.objects.filter(playlist=playlist)
                        .aggregate(max_order=Max("order"))
                        .get("max_order")
                        or 0
                    ) + 1
                    ExercisePlaylistOrdered.objects.create(
                        playlist=playlist,
                        exercise=exercise,
                        order=next_order,
                    )

                # Create transpositions if requested
                create_transpositions = request.POST.get("create_transpositions") in ("true", "on", True)
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

        first_ex = created_exercises[0]
        response_data = {
            "success": True,
            "id": first_ex.id,
            "ids": [ex.id for ex in created_exercises],
            "reviewStatus": first_ex.data.get("score", {}).get("umto", {}).get("metadata", {}).get("analysis_review_status", "none"),
        }
        if playlist:
            response_data.update({"playlistId": playlist.id, "playlistName": playlist.name})
        return JsonResponse(response_data, status=201)

    except Exception as e:
        logger.error(f"Error saving MusicXML: {e}", exc_info=True)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return JsonResponse({"error": str(e)}, status=400)
