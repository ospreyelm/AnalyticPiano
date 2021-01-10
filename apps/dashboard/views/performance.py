from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe
from django_tables2 import RequestConfig, Column

from apps.dashboard.tables import MyActivityTable, MyActivityDetailsTable
from apps.exercises.models import PerformanceData, Playlist

User = get_user_model()


@login_required
def performance_list_view(request, subscriber_id=None):
    subscriber_id = subscriber_id or request.user.id
    subscriber = get_object_or_404(User, id=subscriber_id)

    if not request.user.is_supervisor_to(subscriber):
        raise PermissionDenied
    performances = PerformanceData.objects.filter(
        user=subscriber
    ).select_related('user', 'playlist')

    table = MyActivityTable(
        performances
    )
    subscriber_name = subscriber

    RequestConfig(request).configure(table)
    return render(request, "dashboard/performances-list.html", {
        "table": table,
        "subscriber_name": subscriber_name,
    })


def playlist_pass_bool(exercises_data, playlist_length):
    parsed_data = {}
    for completion in exercises_data:
        c_id = completion['id']
        if c_id not in parsed_data.keys():
            parsed_data[c_id] = []
        parsed_data[c_id].append(completion['exercise_error_tally'])
        del c_id

    playlist_pass = True
    if len(parsed_data.keys()) < playlist_length:
        playlist_pass = False
    else:
        for key in parsed_data:
            least_err = sorted(parsed_data[key])[0]
            if isinstance(least_err, int) and least_err > 0:
                playlist_pass = False
    return playlist_pass


def playlist_pass_date(exercises_data, playlist_length):
    parsed_data = {}
    for completion in exercises_data:
        c_id = completion['id']
        if c_id not in parsed_data.keys():
            parsed_data[c_id] = []
        parsed_data[c_id].append({
            'date': completion['performed_at'],
            'dur': completion['exercise_duration'],
            'err': completion['exercise_error_tally']
        })
        del c_id

    ex_pass_dates = []
    for key in parsed_data:
        error_free = []
        for occasion in parsed_data[key]:
            print(occasion)
            if not isinstance(occasion['err'], int) or occasion['err'] < 6:
                error_free.append(occasion['date'])
        if len(error_free) > 0:
            ex_pass_dates.append(sorted(error_free)[0])

    if len(ex_pass_dates) < playlist_length:
        return None
    else:
        return sorted(ex_pass_dates)[-1] + " GMT"


def playing_time(exercises_data):
    seconds = 0
    for completion in exercises_data:
        seconds += completion['exercise_duration']
        # data gives seconds
    hours = int(seconds // 3600)
    minutes = int((seconds // 60) % 60)
    seconds = int((seconds // 1) % 60)
    if hours >= 2:
        return str(hours) + "+ hrs"
    elif hours == 1:
        return str(hours) + " hrs, " + str(minutes) + " mins"
    elif minutes >= 1:
        return str(minutes) + "+ mins"
    else:
        return str(seconds) + "s"


def playlist_performance_view(request, playlist_id, subscriber_id=None):
    subscriber_id = subscriber_id or request.user.id
    subscriber = get_object_or_404(User, id=subscriber_id)
    if not request.user.is_supervisor_to(subscriber):
        raise PermissionDenied
    subscriber_name = subscriber

    data = []
    performances = PerformanceData.objects.filter(
        playlist__id=playlist_id, user_id=subscriber_id
    ).select_related('user', 'playlist')
    playlist = Playlist.objects.filter(id=playlist_id).first()
    exercises = [exercise for exercise in playlist.exercise_list]
    users_email_list = list(set(list(performances.values_list('user__email', flat=True))))

    for user in users_email_list:
        performance_obj = performances.filter(user__email=user).first()
        user_data = {
            'performer': user,
            'subscriber_id': subscriber_id,
            'playlist_id': playlist.id,
            'playlist_name': playlist.name,
            'playlist_length': len(playlist.exercise_list),
            'performance_obj': performance_obj,
            'performance_data': performance_obj.data,
            'performer_obj': subscriber
        }
        user_data.update({'exercise_count': len(user_data['performance_data'])})
        data.append(user_data)

    for d in data:
        performance_obj = d['performance_obj']
        exercises_data = d['performance_data']

        d['playing_time'] = playing_time(exercises_data)
        d['playlist_pass_bool'] = playlist_pass_bool(exercises_data, d['playlist_length'])
        d['playlist_pass_date'] = playlist_pass_date(exercises_data, d['playlist_length'])

        [d.update(**{exercise['id']: mark_safe(
            f'{"Error(s) " if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else "PASS "}'
            f'<br>'
            f'{performance_obj.get_exercise_first_pass(exercise["id"])}'
            f'<br>'
            f'{"" if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else exercise["exercise_mean_tempo"]}'
            f'{"" if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else "*" * exercise["exercise_tempo_rating"]}'
        )}) for exercise in exercises_data]

    table = MyActivityDetailsTable(
        data=data,
        extra_columns=[(exercises[num], Column(verbose_name=str(num + 1), orderable=False)) for num in
                       range(len(exercises))]
    )

    RequestConfig(request).configure(table)
    return render(request, "dashboard/performance_details.html", {
        "table": table,
        "subscriber_name": subscriber_name,
    })
