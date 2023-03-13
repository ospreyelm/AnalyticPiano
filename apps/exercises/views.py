import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_tables2 import Column

from apps.exercises.models import Course, Playlist, PerformanceData, User as Performers
from apps.exercises.tables import PlaylistActivityTable

User = get_user_model()


@staff_member_required
def playlist_performance_view(request, playlist_id):
    data = []
    performances = PerformanceData.objects.filter(
        playlist__id=playlist_id
    ).select_related("user", "playlist")
    playlist = Playlist.objects.get(id=playlist_id)
    exercises = [exercise for exercise in playlist.exercise_list]
    users = list(set(list(performances.values_list("user__email", flat=True))))

    for user in users:
        name = [
            n
            for n in list(
                Performers.objects.filter(email=user).values_list(
                    "first_name", "last_name"
                )
            )[0]
        ]
        user_data = {
            "email": user,
            "performer": " ".join(
                [
                    n
                    for n in [
                        name[0],
                        name[1].upper(),
                        "<" + user + ">",
                    ]
                    if n != ""
                ]
            ),
            "performance_data": performances.filter(user__email=user).first().data,
        }
        user_data.update({"exercise_count": len(user_data["performance_data"])})
        data.append(user_data)

    for d in data:
        exercises_data = d["performance_data"]

        [
            d.update(
                **{
                    exercise[
                        "id"
                    ]: f'{"Error(s) " if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else "Pass "}'
                    f'{"" if ((isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) or not exercise["exercise_mean_tempo"]) else exercise["exercise_mean_tempo"]}'
                    f'{"" if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else "*" * round(exercise["exercise_tempo_rating"])} '
                }
            )
            for exercise in exercises_data
        ]

    table = PlaylistActivityTable(
        data=data, extra_columns=[(exercise, Column()) for exercise in exercises]
    )

    return render(
        request, "admin/performances.html", {"table": table, "playlist_id": playlist_id}
    )


@login_required
@method_decorator(csrf_exempt)
def submit_exercise_performance(request):
    user_id = request.user.id if request.user.is_authenticated else None
    performance_data = json.loads(request.POST.get("data"))

    data_course_id = performance_data["course_ID"]
    data_playlist_id = performance_data["playlist_ID"]
    data_exercise_num = performance_data["exercise_num"]

    # This shouldn't require a lookup but only a format conversion
    # between integers (0 thru 1,757,599) and strings (A00AA thru Z99ZZ)
    course_id = Course.objects.get(id=data_course_id)._id
    playlist_id = Playlist.objects.get(id=data_playlist_id)._id

    # Convoluted procedure because the Playlist object is not imported to exercise_context.js
    # so the accuracy of this database write depends on the playlist not having changed since
    # the call of compileExerciseReport
    exercise_id = Playlist.objects.filter(id=data_playlist_id).first()\
        .get_exercise_obj_by_num(int(data_exercise_num)).id

    # Intercept this meaningless prop from being written to the database
    performance_data.pop("exercise_num")

    PerformanceData.submit(
        user_id = user_id, # integer
        course_id = course_id, # integer
        playlist_id = playlist_id, # integer
        exercise_id = exercise_id, # string
        data = performance_data,
    )
    return HttpResponse(status=201)


@login_required
@method_decorator(csrf_exempt)
def submit_playlist_performance(request):
    # IS THIS OBSOLETE?
    user_id = request.user.id if request.user.is_authenticated else None
    performance_data = json.loads(request.POST.get("data"))

    data_playlist_id = performance_data["playlist_ID"]

    # This shouldn't require a lookup but only a format conversion
    # between integers (0 thru 1,757,599) and strings (A00AA thru Z99ZZ)
    playlist_id = Playlist.objects.get(name=data_playlist_id)._id

    # Intercept this meaningless prop from being written to the database
    performance_data.pop("exercise_num")

    PerformanceData.submit_playlist_performance(
        user_id = user_id, # integer
        playlist_id = playlist_id, # integer
        data = performance_data,
    )
    return HttpResponse(status=201)
