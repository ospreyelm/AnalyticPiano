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

@login_required
def workbench_view(request):
    """
    Renders the Teacher Workbench frontend interface.
    """
    return render(request, "dashboard/workbench.html", {})

@login_required
def workbench_upload_view(request):
    """
    Handles file uploads from the UI and natively invokes the mass_import_performance CLI.
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
                'mass_import_performance', 
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
    
    # Filter by user and 'Auto-Import:' prefix which replaces the problematic 
    # data__source__type='mass_import' exact JSON match lookup that crashes SQLite.
    exercises = Exercise.objects.filter(
        authored_by=request.user,
        description__startswith="Auto-Import:"
    ).order_by('-id')[:limit]
    
    results = []
    for ex in exercises:
        results.append({
            "id": ex.id,
            "description": ex.description,
            "type": ex.data.get("type"),
            "key": ex.data.get("score", {}).get("meta", {}).get("key", "C"),
            "measureRange": f"{ex.data.get('source', {}).get('filename', '')} - Chunk {ex.data.get('source', {}).get('chunk', '?')}"
        })

    return JsonResponse({"results": results})


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

    created_ids = []

    with transaction.atomic():
        for e_id in source_ids:
            try:
                base_ex = Exercise.objects.get(id=e_id, authored_by=request.user)
            except Exercise.DoesNotExist:
                continue

            # Determine the identMode for this specific item
            ident_mode = per_item_modes.get(str(e_id)) or global_ident_mode
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
