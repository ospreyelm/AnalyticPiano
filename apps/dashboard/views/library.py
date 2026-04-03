from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.exercises.forms import CONTENT_TAGS
from apps.exercises.models import Course, Exercise, ExercisePlaylistOrdered, Playlist, PlaylistCourseOrdered


@login_required
def library_view(request):
    """Public content library: lists all is_public courses, playlists, and exercises."""
    type_filter = request.GET.get("type", "all")
    tag_filter = request.GET.get("tag", "")

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
        if tag_filter:
            playlists = playlists.filter(tags__contains=[tag_filter])
    else:
        playlists = Playlist.objects.none()

    if type_filter in ("all", "exercise"):
        exercises = (
            Exercise.objects.filter(is_public=True)
            .select_related("authored_by")
            .order_by("description")
        )
        if tag_filter:
            exercises = exercises.filter(tags__contains=[tag_filter])
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
            "tag_filter": tag_filter,
            "all_tags": CONTENT_TAGS,
        },
    )


@login_required
@require_POST
def clone_course_view(request, course_id):
    """Deep-clone a public course into the current user's account.

    Clones the Course and all its PlaylistCourseOrdered entries (creating new
    Playlist copies per entry), but references Exercises rather than cloning them.
    The clone is set to authored_by=request.user and is_public=False.
    """
    original = get_object_or_404(Course, id=course_id, is_public=True)

    # 1. Clone the Course shell (no M2M yet)
    clone = Course(
        title=f"Copy of {original.title}",
        authored_by=request.user,
        is_public=False,
        open=original.open,
        timely_credit=original.timely_credit,
        tardy_credit=original.tardy_credit,
        late_credit=original.late_credit,
        tardy_threshold=original.tardy_threshold,
    )
    clone.save()

    # 2. For each ordered playlist entry, clone the Playlist and wire it up
    pco_entries = (
        PlaylistCourseOrdered.objects.filter(course=original)
        .select_related("playlist")
        .order_by("order")
    )

    for pco in pco_entries:
        original_playlist = pco.playlist

        # Clone the Playlist (new row, same authored_by = request.user, private)
        new_playlist = Playlist(
            name=original_playlist.name,
            authored_by=request.user,
            is_public=False,
            transpose_requests=list(original_playlist.transpose_requests or []),
            transposition_type=original_playlist.transposition_type,
        )
        new_playlist.save()

        # Re-create ExercisePlaylistOrdered entries referencing original exercises
        orig_epo_entries = (
            ExercisePlaylistOrdered.objects.filter(playlist=original_playlist)
            .select_related("exercise")
            .order_by("order")
        )
        for epo in orig_epo_entries:
            ExercisePlaylistOrdered.objects.create(
                exercise=epo.exercise,
                playlist=new_playlist,
                order=epo.order,
            )

        # Wire playlist into cloned course preserving order and dates
        PlaylistCourseOrdered.objects.create(
            playlist=new_playlist,
            course=clone,
            order=pco.order,
            due_date=pco.due_date,
            publish_date=pco.publish_date,
        )

    messages.success(
        request,
        f"\u201c{original.title}\u201d was copied to your courses as \u201c{clone.title}\u201d.",
    )
    return redirect("dashboard:edit-course", course_id=clone.id)
