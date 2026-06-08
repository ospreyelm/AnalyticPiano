import json
import copy as _copy

import os
import tempfile
from django.core.management import call_command
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from apps.exercises.models import Exercise
from apps.exercises.umto import AnalysisSlice, InteractionMode

CHORDAL_ANALYSIS_TARGETS = {
    "roman_numeral",
    "figured_bass",
    "analysis_match",
    "identification",
}

@login_required
def workbench_view(request):
    """
    Renders the Teacher Workbench frontend interface.
    """
    return render(request, "dashboard/workbench.html", {})

@login_required
def workbench_upload_view(request):
    """
    Handles file uploads from the UI and invokes the MusicXML UMTO router.
    """
    if request.method == 'POST' and request.FILES.get('musicxml_file'):
        uploaded_file = request.FILES['musicxml_file']
        
        # Save to a temporary file for the CLI to read
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as temp:
            for chunk in uploaded_file.chunks():
                temp.write(chunk)
            temp_path = temp.name
            
        try:
            # Route to our CLI command dynamically
            call_command(
                'import_musicxml',
                temp_path, 
                author=request.user.email
            )
        except Exception as e:
            # Handle failure
            print(f"FAILED IMPORT: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    return redirect('dashboard:workbench')

@login_required
def api_recent_imports(request):
    """
    Get the most recent base exercises that were created via mass_import.
    Used by the Teacher Dashboard Workbench.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    limit = int(request.GET.get('limit', 50))
    
    exercises = Exercise.objects.filter(
        authored_by=request.user,
    ).order_by('-_id')[:limit * 3]
    
    results = []
    for ex in exercises:
        data = ex.data or {}
        if not data.get("isUMTO"):
            continue
        score = data.get("score", {})
        umto = score.get("umto", {})
        metadata = umto.get("metadata", {})
        score_kind = metadata.get("score_kind", "voices")
        results.append({
            "id": ex.id,
            "description": ex.description,
            "type": data.get("type"),
            "scoreKind": score_kind,
            "analysisReviewStatus": metadata.get("analysis_review_status", "none"),
            "key": score.get("meta", {}).get("key") or metadata.get("key", "C"),
            "measureRange": metadata.get("source") or data.get("source", {}).get("filename", "Imported MusicXML"),
        })
        if len(results) >= limit:
            break

    return JsonResponse({"results": results})


def _score_kind(exercise):
    return (
        (exercise.data or {})
        .get("score", {})
        .get("umto", {})
        .get("metadata", {})
        .get("score_kind", "voices")
    )


@login_required
@csrf_exempt
def api_chordal_analysis_review(request, exercise_id):
    try:
        exercise = Exercise.objects.get(id=exercise_id, authored_by=request.user)
    except Exercise.DoesNotExist:
        return JsonResponse({"error": "Exercise not found"}, status=404)

    if _score_kind(exercise) != "chordal":
        return JsonResponse({
            "error": "Analysis review is only available for chordal UMTO imports."
        }, status=400)

    data = _copy.deepcopy(exercise.data or {})
    umto = data.get("score", {}).get("umto", {})
    metadata = umto.get("metadata", {})
    chords = umto.get("chords", [])

    if request.method == "GET":
        analysis_by_offset = {
            round(float(item.get("offset", 0.0)), 6): item
            for item in umto.get("analysis", [])
        }
        rows = []
        for chord in chords:
            offset = round(float(chord.get("offset", 0.0)), 6)
            rows.append({
                "offset": offset,
                "duration": chord.get("duration"),
                "visible": chord.get("visible", []),
                "hidden": chord.get("hidden", []),
                "spelling": chord.get("spelling", []),
                "content": (analysis_by_offset.get(offset) or {}).get("content", {}),
            })
        return JsonResponse({
            "exerciseId": exercise.id,
            "description": exercise.description,
            "scoreKind": "chordal",
            "reviewStatus": metadata.get("analysis_review_status", "none"),
            "rows": rows,
        })

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    valid_offsets = {
        round(float(chord.get("offset", 0.0)), 6)
        for chord in chords
    }
    new_analysis = []
    try:
        for row in payload.get("rows", []):
            offset = round(float(row.get("offset", 0.0)), 6)
            if offset not in valid_offsets:
                return JsonResponse({
                    "error": f"Unknown chord offset: {offset}",
                }, status=400)
            slice_data = {
                "offset": offset,
                "content": row.get("content", {}),
                "unit_tags": row.get("unit_tags", []),
                "is_target": True,
            }
            new_analysis.append(AnalysisSlice(**slice_data).model_dump(mode="json"))
            spelling = row.get("spelling")
            if spelling is not None:
                for chord in chords:
                    if round(float(chord.get("offset", 0.0)), 6) == offset:
                        expected = len(chord.get("visible", [])) + len(chord.get("hidden", []))
                        if len(spelling) != expected:
                            return JsonResponse(
                                {"error": f"spelling length {len(spelling)} != {expected} at offset {offset}"},
                                status=400)
                        chord["spelling"] = spelling
                        break
    except (TypeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    metadata["analysis_review_status"] = "reviewed"
    umto["analysis"] = new_analysis
    umto["chords"] = chords
    data["analysis"] = new_analysis
    exercise.data = data
    exercise.save(update_fields=["data"])
    return JsonResponse({
        "status": "success",
        "reviewStatus": "reviewed",
        "analysis": new_analysis,
    })


def _analysis_review_status(exercise):
    return (
        (exercise.data or {})
        .get("score", {})
        .get("umto", {})
        .get("metadata", {})
        .get("analysis_review_status", "none")
    )


def _clone_chordal_projection(base_ex, author, target_type):
    data = _copy.deepcopy(base_ex.data)
    metadata = data["score"]["umto"]["metadata"]
    metadata["exercise_id"] = "TEMP"

    mode = InteractionMode.PLAYBACK
    if target_type == "analysis_match":
        mode = InteractionMode.ANALYSIS_MATCH
    elif target_type != "exact_match":
        mode = InteractionMode.IDENTIFICATION
    metadata["mode"] = mode.value
    data["mode"] = mode.value

    analysis_type_map = {
        "roman_numeral": "roman",
        "figured_bass": "figured_bass",
        "analysis_match": "roman",
        "identification": "note_name",
    }
    if target_type in analysis_type_map:
        data["analysisType"] = analysis_type_map[target_type]

    suffix = f" ({target_type})"
    description = f"{(base_ex.description or base_ex.id)[:60 - len(suffix)]}{suffix}"
    new_ex = Exercise(
        description=description,
        data=data,
        authored_by=author,
        skill_tags=base_ex.skill_tags,
        complexity=base_ex.complexity,
        is_public=False,
        time_signature=metadata.get("meter", ""),
    )
    new_ex.save()
    new_ex.data["score"]["umto"]["metadata"]["exercise_id"] = new_ex.id
    new_ex.save(update_fields=["data"])
    return new_ex


@login_required
@csrf_exempt
def api_multiply_projection(request):
    """
    Takes a set of base exercise IDs and projects them into a target type 
    (figured_bass, roman_numeral, chorale_identification).
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body)
        source_ids = payload.get("source_ids", [])
        target_type = payload.get("target_type")
        global_ident_mode = payload.get("ident_mode", "submit")
        per_item_modes = payload.get("per_item_modes", {}) # { "id": "mode" }
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not source_ids or not target_type:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    source_exercises = []
    for e_id in source_ids:
        try:
            source_exercises.append(Exercise.objects.get(id=e_id, authored_by=request.user))
        except Exercise.DoesNotExist:
            continue

    chordal_sources = [ex for ex in source_exercises if _score_kind(ex) == "chordal"]
    voices_sources = [ex for ex in source_exercises if _score_kind(ex) != "chordal"]
    if chordal_sources and voices_sources:
        return JsonResponse({
            "error": "Mixed chordal and voices projections must be run separately."
        }, status=400)
    if chordal_sources and target_type not in CHORDAL_ANALYSIS_TARGETS | {"exact_match"}:
        return JsonResponse({
            "error": f"Unsupported chordal projection type: {target_type}"
        }, status=400)
    if chordal_sources and target_type in CHORDAL_ANALYSIS_TARGETS:
        unreviewed = [
            ex.id for ex in chordal_sources
            if _analysis_review_status(ex) != "reviewed"
        ]
        if unreviewed:
            return JsonResponse({
                "error": "Chordal analysis projections require reviewed analysis."
            }, status=400)

    created_ids = []

    with transaction.atomic():
        for base_ex in source_exercises:
            if _score_kind(base_ex) == "chordal":
                new_ex = _clone_chordal_projection(base_ex, request.user, target_type)
                created_ids.append(new_ex.id)
                continue

            # Determine the identMode for this specific item
            ident_mode = per_item_modes.get(str(base_ex.id)) or global_ident_mode
            if ident_mode not in ["submit", "practice", "test"]:
                ident_mode = "submit"

            source_data = base_ex.data or {}
            score_data = _copy.deepcopy(source_data.get("score", {}))
            
            from apps.exercises.umto_factory import save_umto_exercise
            from apps.exercises.umto import InteractionMode
            
            # Map target_type to InteractionMode
            mode_map = {
                "roman_numeral":  InteractionMode.IDENTIFICATION,
                "figured_bass":   InteractionMode.IDENTIFICATION,
                "identification": InteractionMode.IDENTIFICATION,
                "analysis_match": InteractionMode.ANALYSIS_MATCH,
                "exact_match":    InteractionMode.PLAYBACK,
            }
            mode = mode_map.get(target_type, InteractionMode.IDENTIFICATION)

            # Safely build description without exceeding the 60 char database limit
            target_suffix = f" ({target_type})"
            max_base_len = 60 - len(target_suffix)
            safe_desc = f"{base_ex.description[:max_base_len]}{target_suffix}"

            # Determine clef from base data or default to keyboard for chorales
            source_clef = source_data.get("clef") or source_data.get("metadata", {}).get("clef") or "keyboard"

            new_ex = save_umto_exercise(
                description=safe_desc,
                score_data=score_data,
                author=request.user,
                skill_tags=base_ex.skill_tags,
                complexity=base_ex.complexity,
                is_public=False,
                umto_kwargs=dict(
                    exercise_id="TEMP",
                    source=f"Projected from {base_ex.id}",
                    key=source_data.get("key") or score_data.get("meta", {}).get("key", "C"),
                    meter=score_data.get("meta", {}).get("time", "4/4"),
                    clef=source_clef,
                    complexity_score=base_ex.complexity,
                    mode=mode,
                    target_voice=None, # Projection assumes SATB/chorale
                )
            )
            created_ids.append(new_ex.id)

    return JsonResponse({
        "status": "success", 
        "created_exercises": created_ids,
        "message": f"Successfully projected {len(created_ids)} exercises into {target_type}."
    })
