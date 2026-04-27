import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django_tables2 import Column

from apps.exercises.models import Course, Playlist, PerformanceData, User as Performers, IdentificationAttempt, Exercise, StudentSkillMastery
from apps.exercises.tables import PlaylistActivityTable
from apps.exercises.mastery import record_attempt
from apps.exercises.taxonomy_reader import TaxonomyReader

User = get_user_model()


def _performance_demonstrates_skill(performance_data: dict) -> bool:
    numerator = performance_data.get("score_numerator")
    denominator = performance_data.get("score_denominator")
    if denominator not in (None, 0):
        return numerator == denominator
    return performance_data.get("error_tally") in (0, -1, "n/a")


def _build_completion_response(*, user_id, playlist, exercise_obj, exercise_num, score_numerator, score_denominator, mastery_changes, error_tally=None):
    unit_n = None
    unit_name = None
    if exercise_obj.skill_tags:
        for t in exercise_obj.skill_tags:
            u = TaxonomyReader.get_unit_for_tag(t)
            if u:
                unit_n = str(u.get("n"))
                unit_name = u.get("name")
                break

    unit_bar_segments = []
    if unit_n:
        unit_dict = TaxonomyReader.get_unit(unit_n)
        if unit_dict:
            unit_tags = unit_dict.get("tags", [])
            if user_id and unit_tags:
                mastery_rows = {
                    m.skill_tag: m.level
                    for m in StudentSkillMastery.objects.filter(
                        user_id=user_id, skill_tag__in=unit_tags
                    )
                }
                for tag in unit_tags:
                    unit_bar_segments.append({
                        "tag": tag,
                        "label": TaxonomyReader.get_skill_label(tag),
                        "level": mastery_rows.get(tag, StudentSkillMastery.LEVEL_NOT_STARTED),
                    })

    next_num = playlist.next_num(int(exercise_num))
    next_exercise_url = None
    if next_num and unit_n:
        next_exercise_url = f"/s/units/{unit_n}/play/?playlist={playlist.id}&exercise_num={next_num}"

    return {
        "status": "ok",
        "mastery_changes": mastery_changes,
        "score_numerator": score_numerator,
        "score_denominator": score_denominator,
        "error_tally": error_tally,
        "skill_name": TaxonomyReader.get_skill_label(exercise_obj.skill_tags[0]) if exercise_obj.skill_tags else None,
        "exercise_num": exercise_num,
        "total_exercises": playlist.exercise_count,
        "next_exercise_url": next_exercise_url,
        "unit_n": unit_n,
        "unit_name": unit_name,
        "unit_bar_segments": unit_bar_segments,
    }


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
@csrf_exempt
def submit_exercise_performance(request):
    import traceback as _tb
    try:
        return _submit_exercise_performance(request)
    except Exception as e:
        # TODO(agent): remove this debug wrapper before deploying to production — it exposes tracebacks in responses
        return JsonResponse({"error": str(e), "traceback": _tb.format_exc()}, status=500)


def _submit_exercise_performance(request):
    user_id = request.user.id if request.user.is_authenticated else None
    performance_data = json.loads(request.POST.get("data"))

    data_course_id = performance_data.get("course_ID")
    data_playlist_id = performance_data["playlist_ID"]
    data_exercise_num = performance_data["exercise_num"]

    # This shouldn't require a lookup but only a format conversion
    # between integers (0 thru 1,757,599) and strings (A00AA thru Z99ZZ)
    try:
        course_id = Course.objects.get(id=data_course_id)._id if data_course_id else None
    except Course.DoesNotExist:
        course_id = None

    playlist_obj = Playlist.objects.get(id=data_playlist_id)
    playlist_id = playlist_obj._id

    # Convoluted procedure because the Playlist object is not imported to exercise_context.js
    # so the accuracy of this database write depends on the playlist not having changed since
    # the call of compileExerciseReport
    exercise_id = playlist_obj.get_exercise_obj_by_num(int(data_exercise_num)).id

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
    correct = _performance_demonstrates_skill(performance_data)
    mastery_changes = {}
    if exercise_obj.skill_tags:
        mastery_changes = record_attempt(user_id=user_id, exercise=exercise_obj, correct=correct)

    response_data = _build_completion_response(
        user_id=user_id,
        playlist=playlist_obj,
        exercise_obj=exercise_obj,
        exercise_num=data_exercise_num,
        score_numerator=performance_data.get("score_numerator"),
        score_denominator=performance_data.get("score_denominator"),
        mastery_changes=mastery_changes,
        error_tally=performance_data.get("error_tally"),
    )
    return JsonResponse(response_data)


@login_required
@csrf_exempt
def identification_answers_view(request):
    if request.method == "POST":
        data = json.loads(request.POST.get("data"))
        data_course_id = data.get("course_ID")
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
            attempt_type=data.get("attempt_type", "practice"),
        )

        if not data.get("is_page_submit", False):
            return JsonResponse({"status": "saved"}, status=201)

        # Record mastery attempt
        # score structure: {"correct": N, "incorrect": N, "unanswered": N}
        score_data = data.get('score', {})
        correct = (score_data.get('incorrect', 1) == 0 and score_data.get('unanswered', 1) == 0)
        mastery_changes = {}
        if exercise.skill_tags:
            mastery_changes = record_attempt(user_id=request.user.id, exercise=exercise, correct=correct)

        total_answered = score_data.get("correct", 0) + score_data.get("incorrect", 0) + score_data.get("unanswered", 0)
        response_data = _build_completion_response(
            user_id=request.user.id,
            playlist=playlist,
            exercise_obj=exercise,
            exercise_num=data_exercise_num,
            score_numerator=score_data.get("correct"),
            score_denominator=total_answered,
            mastery_changes=mastery_changes,
            error_tally=score_data.get("incorrect", 0),
        )

        return JsonResponse(response_data, status=201)

    elif request.method == "GET":
        exercise_id = request.GET.get("exercise_id")
        if not exercise_id:
            return JsonResponse({})
        attempt = (
            IdentificationAttempt.objects.filter(
                user=request.user,
                exercise__id=exercise_id,
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
            "correct_answers": attempt.correct_answers,
            "page_num": attempt.page_num,
            "is_page_submit": attempt.is_page_submit,
            "submitted_at": attempt.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return HttpResponse(status=405)
