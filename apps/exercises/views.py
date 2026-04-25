import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_tables2 import Column

from apps.exercises.models import Course, Playlist, PerformanceData, User as Performers, IdentificationAttempt, Exercise
from apps.exercises.tables import PlaylistActivityTable
from apps.exercises.mastery import record_attempt

User = get_user_model()


# @staff_member_required
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
                    ]: f'{"Error(s) " if (isinstance(exercise["error_tally"], int) and exercise["error_tally"] > 0) else "Pass "}'
                    f'{"" if ((isinstance(exercise["error_tally"], int) and exercise["error_tally"] > 0) or not exercise["tempo_mean_semibreves_per_min"]) else round(exercise["tempo_mean_semibreves_per_min"])}'
                    f'{"" if (isinstance(exercise["error_tally"], int) and exercise["error_tally"] > 0) else "*" * round(exercise["tempo_rating"])} '
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
    try:
        course_id = Course.objects.get(id=data_course_id)._id if data_course_id else None
    except Course.DoesNotExist:
        course_id = None

    playlist_id = Playlist.objects.get(id=data_playlist_id)._id

    # Convoluted procedure because the Playlist object is not imported to exercise_context.js
    # so the accuracy of this database write depends on the playlist not having changed since
    # the call of compileExerciseReport
    exercise_id = (
        Playlist.objects.filter(id=data_playlist_id)
        .first()
        .get_exercise_obj_by_num(int(data_exercise_num))
        .id
    )

    # Intercept this meaningless prop from being written to the database
    performance_data.pop("exercise_num")

    PerformanceData.submit(
        user_id=user_id,  # integer
        course_id=course_id,  # integer
        playlist_id=playlist_id,  # integer
        exercise_id=exercise_id,  # string
        data=performance_data,
    )

    # Record mastery attempt
    exercise_obj = Exercise.objects.get(id=exercise_id[:6])
    correct = performance_data.get('error_tally') in (0, -1, 'n/a')
    mastery_changes = {}
    if exercise_obj.skill_tags:
        mastery_changes = record_attempt(user_id=user_id, exercise=exercise_obj, correct=correct)

    from apps.exercises.taxonomy_reader import TaxonomyReader
    unit_n = None
    if exercise_obj.skill_tags:
        for t in exercise_obj.skill_tags:
            u = TaxonomyReader.get_unit_for_tag(t)
            if u:
                unit_n = str(u.get("n"))
                break

    response_data = {"status": "ok", "mastery_changes": mastery_changes}
    if unit_n:
        response_data["unit_n"] = unit_n
        
    return JsonResponse(response_data)


@login_required
@csrf_exempt
def identification_answers_view(request):
    if request.method == "POST":
        data = json.loads(request.POST.get("data"))
        data_course_id = data["course_ID"]
        data_playlist_id = data["playlist_ID"]
        data_exercise_num = data["exercise_num"]

        try:
            course = Course.objects.get(id=data_course_id) if data_course_id else None
            playlist = Playlist.objects.get(id=data_playlist_id)
            exercise = playlist.get_exercise_obj_by_num(int(data_exercise_num))
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

        IdentificationAttempt.objects.create(
            user=request.user,
            exercise=exercise,
            course=course,
            playlist=playlist,
            answers=data.get("answers", {}),
            correctness=data.get("correctness", {}),
            score=data.get("score", {}),
            correct_answers=data.get("correct_answers", {}),
            page_num=data.get("page_num"),
            is_page_submit=data.get("is_page_submit", False),
            mode=data.get("mode", ""),
        )

        # Record mastery attempt
        # score structure: {"correct": N, "incorrect": N, "unanswered": N}
        score_data = data.get('score', {})
        correct = (score_data.get('incorrect', 1) == 0 and score_data.get('unanswered', 1) == 0)
        if exercise.skill_tags:
            record_attempt(user_id=request.user.id, exercise=exercise, correct=correct)

        return HttpResponse(status=201)

    elif request.method == "GET":
        exercise_id = request.GET.get("exercise_id")
        if not exercise_id:
            return JsonResponse({})
        attempt = (
            IdentificationAttempt.objects.filter(
                user=request.user,
                exercise_id=exercise_id,
            )
            .order_by("-submitted_at")
            .first()
        )
        if not attempt:
            return JsonResponse({})
        return JsonResponse({
            "answers": attempt.answers,
            "correctness": attempt.correctness,
            "score": attempt.score,
            "page_num": attempt.page_num,
            "submitted_at": attempt.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return HttpResponse(status=405)
