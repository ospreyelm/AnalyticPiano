from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from apps.exercises.models import Course, Exercise, Playlist


@login_required
def library_view(request):
    """Public content library: lists all is_public courses, playlists, and exercises."""
    type_filter = request.GET.get("type", "all")

    if type_filter in ("all", "course"):
        courses = (
            Course.objects.filter(is_public=True)
            .select_related("authored_by")
            .annotate(playlist_count=Count("playlists", distinct=True))
            .order_by("title")
        )
    else:
        courses = Course.objects.none()

    if type_filter in ("all", "playlist"):
        playlists = (
            Playlist.objects.filter(is_public=True)
            .select_related("authored_by")
            .annotate(exercise_count=Count("exercises", distinct=True))
            .order_by("name")
        )
    else:
        playlists = Playlist.objects.none()

    if type_filter in ("all", "exercise"):
        exercises = (
            Exercise.objects.filter(is_public=True)
            .select_related("authored_by")
            .order_by("description")
        )
    else:
        exercises = Exercise.objects.none()

    return render(
        request,
        "dashboard/library.html",
        {
            "courses": courses,
            "playlists": playlists,
            "exercises": exercises,
            "type_filter": type_filter,
        },
    )
