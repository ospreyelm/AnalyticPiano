from copy import copy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django_tables2 import RequestConfig


from apps.dashboard.forms import DashboardExerciseForm
from apps.dashboard.tables import ExercisesListTable
from apps.exercises.models import Exercise


@login_required
def exercises_list_view(request):
    exercises = Exercise.objects.filter(authored_by=request.user).select_related(
        "authored_by"
    )

    table = ExercisesListTable(exercises)
    exercises_author = request.user

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(
        request,
        "dashboard/exercises-list.html",
        {"table": table, "exercises_author": exercises_author},
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
    }

    PROTECT_EXERCISE_CONTENT = exercise.has_been_performed

    if request.method == "POST":
        form = DashboardExerciseForm(data=request.POST, instance=exercise)
        form.context = {"user": request.user}
        if form.is_valid():
            if PROTECT_EXERCISE_CONTENT:
                ## only alter is_public, description fields
                ## under no circumstances allow other changes to data
                exercise.save(update_fields=["description", "is_public"])
                ## ^ is this ok?
            else:
                exercise = form.save(commit=False)
                exercise.authored_by = request.user
                ## ^ original authorship of exercise should not change
                exercise.save()

            if "save-and-continue" in request.POST:
                success_url = reverse(
                    "dashboard:edit-exercise", kwargs={"exercise_id": exercise.id}
                )
                messages.add_message(
                    request, messages.SUCCESS, f"{context['verbose_name']} saved"
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
                exercise.save()
                return redirect("dashboard:edit-exercise", exercise.id)
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

    context = {
        "obj": exercise,
        "obj_name": exercise.id,
        "verbose_name": exercise._meta.verbose_name,
        "verbose_name_plural": exercise._meta.verbose_name_plural,
        "has_been_performed": exercise.has_been_performed,
        "redirect_url": reverse("dashboard:exercises-list"),
    }
    return render(request, "dashboard/delete-confirmation.html", context)
