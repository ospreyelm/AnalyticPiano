import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_tables2 import Column

from apps.exercises.models import Playlist, PerformanceData
from apps.exercises.tables import AdminPlaylistPerformanceTable

User = get_user_model()


@staff_member_required
def playlist_performance_view(request, playlist_id):
    data = []
    performances = PerformanceData.objects.filter(
        playlist__id=playlist_id
    ).select_related('user', 'playlist')
    playlist = Playlist.objects.filter(id=playlist_id).first()
    exercises = [exercise for exercise in playlist.exercise_list]
    users = list(set(list(performances.values_list('user__email', flat=True))))

    for user in users:
        user_data = {
            'email': user,
            'performance_data': performances.filter(user__email=user).first().data
        }
        user_data.update({'exercise_count': len(user_data['performance_data'])})
        data.append(user_data)

    for d in data:
        exercises_data = d['performance_data']

        # format is: [mean tempo, rounded to integer][tempo star-rating] (err count).
        # example: 66** (2)
        [d.update(**{exercise['id']:
            f'{"Error(s) " if ( isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0 ) else "Pass "}'
            f'{"" if ( isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0 ) else exercise["exercise_mean_tempo"]}'
            f'{"" if ( isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0 ) else "*" * exercise["exercise_tempo_rating"]} '
            }) for exercise in exercises_data]

    table = AdminPlaylistPerformanceTable(
        data=data,
        extra_columns=[(exercise, Column()) for exercise in exercises]
    )

    return render(request, "admin/performances.html", {
        "table": table
    })


@login_required
@method_decorator(csrf_exempt)
def submit_exercise_performance(request):
    performance_data = json.loads(request.POST.get('data'))

    user = request.user if request.user.is_authenticated else User.get_guest_user()

    playlist_name, exercise_num = performance_data['exercise_ID'].split('/')
    performance_data.pop('exercise_ID')
    performance_data.pop('performer')

    playlist = Playlist.objects.filter(name=playlist_name).first()
    exercise = playlist.get_exercise_obj_by_num(int(exercise_num))
    PerformanceData.submit(
        playlist_id=playlist._id,
        exercise_id=exercise.id,
        user_id=user.id,
        data=performance_data
    )
    return HttpResponse(status=201)


@method_decorator(csrf_exempt)
def submit_playlist_performance(request):
    performance_data = json.loads(request.POST.get('data'))

    user = request.user if request.user.is_authenticated else User.get_guest_user()

    playlist_name, _ = performance_data['exercise_ID'].split('/')
    performance_data.pop('exercise_ID')

    playlist = Playlist.objects.filter(name=playlist_name).first()
    PerformanceData.submit_playlist_performance(
        playlist_id=playlist._id,
        user_id=user.id,
        data=performance_data
    )
    return HttpResponse(status=201)
