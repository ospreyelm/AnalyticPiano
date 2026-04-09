from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.exercises.models import Course, PerformanceData, PlaylistCourseOrdered
from apps.exercises.utils.recurrence import get_recurring_assignment_snapshot

# Maps performance_dict mark codes to student-facing labels and badge classes
MARK_DISPLAY = {
    "P": ("On Time", "badge-success"),
    "T": ("Tardy", "badge-warning"),
    "L": ("Late", "badge-danger"),
    "C": ("Complete", "badge-success"),
    "X": ("Incomplete", "badge-secondary"),
}


@login_required
def my_work_view(request):
    """Show only courses the logged-in student is enrolled in via Group membership."""
    enrolled_courses = (
        Course.objects.filter(visible_to__members=request.user)
        .select_related("authored_by")
        .distinct()
    )

    # Fetch all performance data for this user across enrolled courses in one query
    perf_map = {
        (pd.course_id, pd.playlist_id): pd
        for pd in PerformanceData.objects.filter(
            user=request.user, course__in=enrolled_courses
        ).select_related("playlist")
    }

    # Build per-course data: playlists with completion status and due dates
    courses_data = []
    for course in enrolled_courses:
        playlists_data = []
        pcos = PlaylistCourseOrdered.objects.filter(
            course=course
        ).select_related("playlist").order_by("order")

        # Look up this student's marks from the cached performance_dict
        student_marks = course.performance_dict.get(str(request.user), {})

        for pco in pcos:
            playlist = pco.playlist
            due_date = pco.due_date

            if pco.is_recurring:
                recurring = get_recurring_assignment_snapshot(request.user, pco)
                playlists_data.append(
                    {
                        "playlist": playlist,
                        "due_date": due_date,
                        "passed": recurring["target_met"],
                        "pass_date": None,
                        "mark_code": None,
                        "mark_label": recurring["progress_label"],
                        "mark_class": (
                            "badge-success"
                            if recurring["target_met"]
                            else "badge-warning"
                        ),
                        "course_id": course.id,
                        "is_recurring": True,
                        "completed_periods": recurring["completed_periods"],
                        "next_reset_at": recurring["next_reset_at"],
                    }
                )
                continue

            perf = perf_map.get((course.pk, playlist.pk))
            if perf is not None:
                passed = perf.playlist_passed()
                pass_date = perf.playlist_pass_date if passed else None
            else:
                passed = False
                pass_date = None

            # Get mark code (P/T/L/C/X) from performance_dict if the student has passed
            mark_code = student_marks.get(playlist.id) if passed else None
            mark_label, mark_class = MARK_DISPLAY.get(mark_code, ("Complete", "badge-success")) if mark_code else (None, None)

            playlists_data.append(
                {
                    "playlist": playlist,
                    "due_date": due_date,
                    "passed": passed,
                    "pass_date": pass_date,
                    "mark_code": mark_code,
                    "mark_label": mark_label,
                    "mark_class": mark_class,
                    "course_id": course.id,
                    "is_recurring": False,
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
