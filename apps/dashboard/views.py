from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404
from django.shortcuts import render
from django_tables2 import Column
from django_tables2 import RequestConfig

from apps.dashboard.forms import AddSupervisorForm, AddSubscriberForm
from apps.dashboard.tables import SupervisorsTable, SubscribersTable, PerformancesListTable, \
    SubscriberPlaylistPerformanceTable
from apps.exercises.models import Playlist, PerformanceData

User = get_user_model()


def dashboard_index_view(request):
    raise NotImplemented


@login_required
def supervisors_view(request):
    if request.method == 'POST':
        form = AddSupervisorForm(data={'email': request.POST.get('email')})
        if form.is_valid():
            supervisor = get_object_or_404(User, email=form.cleaned_data['email'])
            request.user.subscribe_to(supervisor)
            return redirect('dashboard:supervisors')
    else:
        form = AddSupervisorForm()

    supervisors_table = SupervisorsTable([{"supervisor": x} for x in request.user.supervisors])
    RequestConfig(request).configure(supervisors_table)

    return render(request, "dashboard/supervisors.html", {
        "form": form, "table": supervisors_table
    })


@login_required
def subscribers_view(request):
    if request.method == 'POST':
        form = AddSubscriberForm(data={'email': request.POST.get('email')})
        if form.is_valid():
            subscriber = get_object_or_404(User, email=form.cleaned_data['email'])
            subscriber.subscribe_to(request.user)
            return redirect('dashboard:subscribers')
    else:
        form = AddSubscriberForm()
    subscribers_table = SubscribersTable([{"subscriber": x} for x in request.user.subscribers])
    RequestConfig(request).configure(subscribers_table)

    return render(request, "dashboard/supervisors.html", {
        "form": form, "table": subscribers_table
    })


@login_required
def unsubscribe_view(request, supervisor_id):
    supervisor = get_object_or_404(User, id=supervisor_id)
    request.user.unsubscribe_from(supervisor)
    return redirect('dashboard:supervisors')


@login_required
def remove_subscriber_view(request, subscriber_id):
    subscriber = get_object_or_404(User, id=subscriber_id)
    subscriber.unsubscribe_from(request.user)
    return redirect('dashboard:subscribers')


@login_required
def performance_list_view(request, subscriber_id=None):
    subscriber_id = subscriber_id or request.user.id
    subscriber = get_object_or_404(User, id=subscriber_id)
    if not request.user.is_supervisor_to(subscriber):
        raise PermissionDenied
    performances = PerformanceData.objects.filter(
        user=subscriber
    ).select_related('user', 'playlist')

    table = PerformancesListTable(
        performances
    )

    return render(request, "dashboard/performances.html", {
        "table": table
    })


def playlist_performance_view(request, playlist_id, subscriber_id=None):
    subscriber_id = subscriber_id or request.user.id
    subscriber = get_object_or_404(User, id=subscriber_id)
    if not request.user.is_supervisor_to(subscriber):
        raise PermissionDenied

    data = []
    performances = PerformanceData.objects.filter(
        playlist__id=playlist_id, user_id=subscriber_id
    ).select_related('user', 'playlist')
    playlist = Playlist.objects.filter(id=playlist_id).first()
    exercises = [exercise for exercise in playlist.exercise_list]
    users = list(set(list(performances.values_list('user__email', flat=True))))

    for user in users:
        user_data = {
            'performer': user,
            'subscriber_id': subscriber_id,
            'playlist_id': playlist.id,
            'performance_data': performances.filter(user__email=user).first().data
        }
        user_data.update({'exercise_count': len(user_data['performance_data'])})
        data.append(user_data)

    for d in data:
        exercises_data = d['performance_data']

        # format is: [mean tempo, rounded to integer][tempo star-rating] (err count).
        # example: 66** (2)
        [d.update(**{exercise['id']: f'{exercise["exercise_mean_tempo"]}'
                                     f'{"*" * exercise["exercise_tempo_rating"]} '
                                     f'({exercise["exercise_error_tally"]})'}) for exercise in exercises_data]

    table = SubscriberPlaylistPerformanceTable(
        data=data,
        extra_columns=[(exercise, Column()) for exercise in exercises]
    )

    return render(request, "dashboard/performances.html", {
        "table": table
    })