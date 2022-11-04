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
                    f'{"" if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else "*" * exercise["exercise_tempo_rating"]} '
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
    performance_data = json.loads(request.POST.get("data"))

    user = request.user if request.user.is_authenticated else User.get_guest_user()

    playlist_name, exercise_num = performance_data["exercise_ID"].split("/")
    performance_data.pop("exercise_ID")
    # performance_data.pop('performer')

    # TODO: change this
    playlist = Playlist.objects.filter(id=playlist_name).first()
    exercise = playlist.get_exercise_obj_by_num(int(exercise_num))
    course = Course.objects.get(id=performance_data["course_ID"])

    PerformanceData.submit(
        course_id=course._id,
        playlist_id=playlist._id,
        exercise_id=exercise.id,
        user_id=user.id,
        data=performance_data,
    )
    return HttpResponse(status=201)


@method_decorator(csrf_exempt)
def submit_playlist_performance(request):
    performance_data = json.loads(request.POST.get("data"))

    user = request.user if request.user.is_authenticated else User.get_guest_user()

    playlist_name, _ = performance_data["exercise_ID"].split("/")
    performance_data.pop("exercise_ID")
    # TODO: change this
    playlist = Playlist.objects.filter(name=playlist_name).first()
    PerformanceData.submit_playlist_performance(
        playlist_id=playlist._id, user_id=user.id, data=performance_data
    )
    return HttpResponse(status=201)
