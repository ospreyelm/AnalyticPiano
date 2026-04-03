from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.exercises.models import Course, PerformanceData, PlaylistCourseOrdered


@login_required
def my_work_view(request):
    """Show only courses the logged-in student is enrolled in via Group membership."""
    enrolled_courses = (
        Course.objects.filter(visible_to__members=request.user)
        .select_related("authored_by")
        .prefetch_related("playlists")
        .distinct()
    )

    # Build per-course data: playlists with completion status and due dates
    courses_data = []
    for course in enrolled_courses:
        playlists_data = []
        pcos = PlaylistCourseOrdered.objects.filter(
            course=course
        ).select_related("playlist").order_by("order")

        for pco in pcos:
            playlist = pco.playlist
            due_date = pco.due_date

            try:
                perf = PerformanceData.objects.get(
                    user=request.user, playlist=playlist, course=course
                )
                passed = perf.playlist_passed()
                pass_date = perf.playlist_pass_date if passed else None
            except PerformanceData.DoesNotExist:
                passed = False
                pass_date = None

            playlists_data.append(
                {
                    "playlist": playlist,
                    "due_date": due_date,
                    "passed": passed,
                    "pass_date": pass_date,
                    "course_id": course.id,
                }
            )

        total = len(playlists_data)
        completed = sum(1 for p in playlists_data if p["passed"])
        courses_data.append(
            {
                "course": course,
                "playlists": playlists_data,
                "total": total,
                "completed": completed,
            }
        )

    return render(
        request,
        "dashboard/my-work.html",
        {"courses_data": courses_data},
    )
