from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django_tables2 import RequestConfig

from apps.dashboard.forms import DashboardExerciseForm
from apps.dashboard.tables import ExercisesListTable
from apps.exercises.models import Exercise


@login_required
def exercises_list_view(request):
    exercises = Exercise.objects.filter(
        authored_by=request.user
    ).select_related('authored_by')

    table = ExercisesListTable(exercises)

    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    return render(request, "dashboard/exercises-list.html", {
        "table": table,
    })


@login_required
def exercise_add_view(request):
    if request.method == 'POST':
        form = DashboardExerciseForm(data=request.POST)
        form.context = {'user': request.user}
        if form.is_valid():
            exercise = form.save(commit=False)
            exercise.authored_by = request.user
            exercise.save()
            return redirect('dashboard:exercises-list')
    else:
        form = DashboardExerciseForm()

    return render(request, "dashboard/exercise.html", {
        "form": form
    })


@login_required
def exercise_edit_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id)

    if request.method == 'POST':
        form = DashboardExerciseForm(data=request.POST, instance=exercise)
        form.context = {'user': request.user}
        if form.is_valid():
            exercise = form.save(commit=False)
            exercise.authored_by = request.user
            exercise.save()
            return redirect('dashboard:exercises-list')
    else:
        form = DashboardExerciseForm(instance=exercise)

    return render(request, "dashboard/exercise.html", {
        "form": form
    })


@login_required
def exercise_delete_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id)
    if exercise.authored_by != request.user:
        raise PermissionDenied

    if exercise.has_been_performed:
        raise ValidationError('Exercises that have been performed cannot be deleted.')

    exercise.delete()
    return redirect('dashboard:exercises-list')
