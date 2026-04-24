import copy as _copy
from copy import copy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django_tables2 import RequestConfig

from apps.dashboard.filters import ListIDFilter, ExerciseListDescriptionFilter
from apps.dashboard.forms import DashboardExerciseForm
from apps.dashboard.tables import ExercisesListTable
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.pitch_voice_utils import strip_to_voice
from apps.exercises.models import Exercise

import re

PITCH_ANALYSIS_TYPES = {
    "note_name",
    "solfege",
    "do_based_solfege",
    "scale_degree",
    "fixed_do",
    "pitch_class",
}

@login_required
def exercises_list_view(request):
    exercises_author = request.user
    exercises = Exercise.objects.filter(authored_by=exercises_author).select_related(
        "authored_by"
    )
    me = request.user

    exercise_id_filter = ListIDFilter(queryset=exercises, data=request.GET)
    exercise_id_filter.form.is_valid()

    min_id = exercise_id_filter.form.cleaned_data["min_id"]
    max_id = exercise_id_filter.form.cleaned_data["max_id"]

    eid_regex = re.compile(r'^E[A-Z][0-9]{2}[A-Z]{2}$')
    if min_id:
        min_id = 'EA00AA'[:max(0,6-len(min_id)):] + min_id.upper()[:6]
        if eid_regex.match(min_id):
            exercises = exercises.filter(id__gte=min_id.upper())
    if max_id and len(max_id) > 0: # should be redundant
        max_id = 'EA00AA'[:max(0,6-len(max_id)):] + max_id.upper()[:6]
        if eid_regex.match(max_id):
            exercises = exercises.filter(id__lte=max_id.upper())

    exercise_description_filter = ExerciseListDescriptionFilter(
        queryset=exercises, data=request.GET
    )
    exercise_description_filter.form.is_valid()

    description_search = exercise_description_filter.form.cleaned_data["description"]
    if description_search:
        exercises = exercises.filter(description__contains=description_search) # __icontains to ignore case

    table = ExercisesListTable(exercises)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(
        request,
        "dashboard/exercises-list.html",
        {
            "table": table,
            "exercises_author": exercises_author,
            "me": me,
            "filters": {
                "id": exercise_id_filter,
                "description": exercise_description_filter,
            },
        },
    )


@login_required
def exercise_add_view(request):
    context = {
        "verbose_name": Exercise._meta.verbose_name,
        "verbose_name_plural": Exercise._meta.verbose_name_plural,
    }

    if request.method == "POST":
        clone_data = request.session.pop("clone_data", None)
        if not clone_data:
            return redirect("dashboard:exercises-list")
        form = DashboardExerciseForm(data=request.POST)
        form.context = {"user": request.user}
        if form.is_valid():
            exercise = form.save(commit=False)
            exercise.authored_by = request.user
            exercise.save()
            if "save-and-continue" in request.POST:
                success_url = reverse(
                    "dashboard:edit-exercise", kwargs={"exercise_id": exercise.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been saved successfully.",
                )
            else:
                success_url = reverse("dashboard:exercises-list")
            return redirect(success_url)
        context["form"] = form
        return render(request, "dashboard/content.html", context)
    else:
        if not request.session.get("clone_data"):
            return redirect("dashboard:exercises-list")

        clone_data = request.session.get("clone_data")
        form = DashboardExerciseForm(initial=clone_data)

    context["form"] = form
    return render(request, "dashboard/content.html", context)


@login_required
def exercise_edit_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id)

    if request.user != exercise.authored_by:
        raise PermissionDenied

    context = {
        "verbose_name": exercise._meta.verbose_name,
        "verbose_name_plural": exercise._meta.verbose_name_plural,
        "has_been_performed": exercise.has_been_performed,
        "preview_url": request.build_absolute_uri(
            reverse("lab:exercise-view", kwargs={"exercise_id": exercise.id})
        ),
        "redirect_url": reverse("dashboard:exercises-list"),
        "delete_url": reverse(
            "dashboard:delete-exercise", kwargs={"exercise_id": exercise_id}
        ),
        "is_chorale": (exercise.data or {}).get("type") == "chorale",
    }

    PROTECT_EXERCISE_CONTENT = exercise.has_been_performed

    if request.method == "POST":
        form = DashboardExerciseForm(data=request.POST, instance=exercise)
        form.context = {"user": request.user}
        if form.is_valid():
            if PROTECT_EXERCISE_CONTENT:
                ## only alter is_public, description fields
                ## under no circumstances allow other changes to data
                exercise.save(update_fields=["is_public", "description"])
                ## ^ is this ok?
            else:
                exercise = form.save(commit=False)
                exercise.authored_by = request.user
                ## ^ original authorship of exercise should not change
                exercise.save()

            if "save-and-preview" in request.POST:
                return redirect(context["preview_url"])
            elif "save-and-continue" in request.POST:
                success_url = reverse(
                    "dashboard:edit-exercise", kwargs={"exercise_id": exercise.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been saved successfully.",
                )
            elif "save-and-edit-previous" in request.POST:
                success_url = reverse(
                    "dashboard:edit-exercise",
                    kwargs={
                        "exercise_id": exercise.get_previous_authored_exercise().id
                    },
                )
            elif "save-and-edit-next" in request.POST:
                success_url = reverse(
                    "dashboard:edit-exercise",
                    kwargs={"exercise_id": exercise.get_next_authored_exercise().id},
                )
            elif "duplicate" in request.POST:
                exercise.pk = None
                exercise.id = None
                exercise.locked = False
                exercise.save()
                return redirect("dashboard:edit-exercise", exercise.id)
            elif "duplicate-as-identification" in request.POST:
                source_data = exercise.data or {}
                score_data = _copy.deepcopy(source_data.get("score", {}))
                intro = source_data.get("introText") or "Label the harmony for each onset."
                
                new_exercise = save_umto_exercise(
                    description=f"{exercise.description or exercise.id} (id)",
                    score_data=score_data,
                    author=request.user,
                    skill_tags=exercise.skill_tags,
                    complexity=exercise.complexity,
                    is_public=exercise.is_public,
                    umto_kwargs=dict(
                        exercise_id="TEMP",
                        source=intro,
                        key=source_data.get("key") or score_data.get("meta", {}).get("key", "C"),
                        meter=score_data.get("meta", {}).get("time", "4/4"),
                        clef=score_data.get("meta", {}).get("clef", "keyboard"),
                        complexity_score=exercise.complexity,
                        mode=InteractionMode.ANALYSIS_MATCH,
                    )
                )
                return redirect("dashboard:edit-exercise", new_exercise.id)
            elif "duplicate-as-pitch-identification" in request.POST:
                source_data = exercise.data or {}
                source_score = _copy.deepcopy(source_data.get("score", {}))
                analysis_type = request.POST.get("analysisType", "")
                ident_mode = request.POST.get("identMode") or "submit"
                voices = request.POST.getlist("voices[]") or request.POST.getlist("voices")

                if analysis_type not in PITCH_ANALYSIS_TYPES:
                    messages.error(request, "Invalid pitch analysis type.")
                    return redirect("dashboard:edit-exercise", exercise.id)

                try:
                    with transaction.atomic():
                        if not voices:
                            raise ValueError("Select at least one voice for pitch identification duplication.")

                        for voice in voices:
                            stripped_score = strip_to_voice(source_score, voice)
                            intro = source_data.get("introText") or f"Name each note in the {voice} voice."
                            
                            new_exercise = save_umto_exercise(
                                description=f"{exercise.description or exercise.id} ({voice} id)",
                                score_data=stripped_score,
                                author=request.user,
                                skill_tags=exercise.skill_tags,
                                complexity=exercise.complexity,
                                is_public=exercise.is_public,
                                umto_kwargs=dict(
                                    exercise_id="TEMP",
                                    source=intro,
                                    key=source_data.get("key") or source_score.get("meta", {}).get("key", "C"),
                                    meter=source_score.get("meta", {}).get("time", "4/4"),
                                    clef=source_score.get("meta", {}).get("clef", "treble"),
                                    complexity_score=exercise.complexity,
                                    mode=InteractionMode.IDENTIFICATION,
                                    target_voice=voice,
                                )
                            )
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect("dashboard:edit-exercise", exercise.id)

                return redirect("dashboard:exercises-list")
            else:
                success_url = reverse("dashboard:exercises-list")
            return redirect(success_url)
        context["form"] = form

    exercise.refresh_from_db()
    form = DashboardExerciseForm(instance=exercise)

    # if exercise.has_been_performed:
    #     ## CAUSES BIG PROBLEMS! DESTROYS FORM VALIDATION
    #     form = DashboardExerciseForm(instance=exercise, disable_fields=True)

    context["form"] = form
    return render(request, "dashboard/edit-exercise.html", context)


@login_required
def exercise_delete_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id)

    if request.user != exercise.authored_by:
        raise PermissionDenied

    if request.method == "POST":
        if exercise.has_been_performed:
            raise ValidationError(
                "Exercises that have been performed cannot be deleted."
            )
        exercise.delete()
        return redirect("dashboard:exercises-list")

        redirect_url = reverse("dashboard:exercises-list")
    
    context = {
        "obj": exercise,
        "obj_name": exercise.id,
        "verbose_name": exercise._meta.verbose_name,
        "verbose_name_plural": exercise._meta.verbose_name_plural,
        "has_been_performed": exercise.has_been_performed,
        "redirect_url": redirect_url,
    }
    return render(request, "dashboard/delete-confirmation.html", context)

import json
from django.http import JsonResponse

@login_required
def api_bulk_delete_exercises(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        ids = data.get("ids", [])
        if not ids:
            return JsonResponse({"error": "No exercise IDs provided."}, status=400)
            
        deleted_count = 0
        from django.db import transaction
        
        with transaction.atomic():
            exercises = Exercise.objects.filter(pk__in=ids)
            for ex in exercises:
                # Security: Only owner can delete
                if ex.authored_by != request.user:
                    continue
                # Protection: Don't delete if performed
                if ex.has_been_performed:
                    continue
                
                ex.delete()
                deleted_count += 1
                
        return JsonResponse({"status": "success", "deleted": deleted_count})
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
