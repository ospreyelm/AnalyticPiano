from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http.response import HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django_tables2 import Column
from django_tables2 import RequestConfig

from apps.dashboard.forms import AddSupervisorForm, AddSubscriberForm
from apps.dashboard.tables import SupervisorsTable, SubscribersTable, PerformancesListTable, \
    SubscriberPlaylistPerformanceTable
from apps.exercises.models import Playlist, PerformanceData
from .forms import KeyboardForm

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
    curr_user = request.user # rewrite to also take parameter
    if not request.user.is_supervisor_to(subscriber):
        raise PermissionDenied
    performances = PerformanceData.objects.filter(
        user=subscriber
    ).select_related('user', 'playlist')

    table = PerformancesListTable(
        performances
    )
    subscriber_name = subscriber
    
    kbd_size_form = KeyboardForm()
    if subscriber.keyboard_size:
        kbd_size_form.fields['keyboard_size'].initial = curr_user.keyboard_size

    if request.method == 'POST':
        kbd_size_form = KeyboardForm(request.POST)
        if kbd_size_form.is_valid() and not curr_user.is_anonymous:
            curr_user.keyboard_size = kbd_size_form.cleaned_data['keyboard_size']
            curr_user.save()
        return HttpResponseRedirect('/dashboard/performances/') # should be rewritten properly as reload; '' seemed not to work
    
    RequestConfig(request).configure(table)
    return render(request, "dashboard/performances-list.html", {
        "table": table,
        "subscriber_name": subscriber_name,
        "form": kbd_size_form
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
    users_email_list = list(set(list(performances.values_list('user__email', flat=True))))

    for user in users_email_list:
        performance_obj = performances.filter(user__email=user).first()
        user_data = {
            'performer': user,
            'subscriber_id': subscriber_id,
            'playlist_id': playlist.id,
            'playlist_name': playlist.name,
            'performance_obj': performance_obj,
            'performance_data': performance_obj.data,
            'performer_obj': subscriber
        }
        user_data.update({'exercise_count': len(user_data['performance_data'])})
        data.append(user_data)

    for d in data:
        performance_obj = d['performance_obj']
        exercises_data = d['performance_data']

        [d.update(**{exercise['id']: mark_safe(
            f'{"Error(s) " if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else "Pass "}'
            f'{"" if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else exercise["exercise_mean_tempo"]}'
            f'{"" if (isinstance(exercise["exercise_error_tally"], int) and exercise["exercise_error_tally"] > 0) else "*" * exercise["exercise_tempo_rating"]}'
            f'<br>'
            f'{performance_obj.get_exercise_first_pass(exercise["id"])}'
        )}) for exercise in exercises_data]

    table = SubscriberPlaylistPerformanceTable(
        data=data,
        extra_columns=[(exercise, Column()) for exercise in exercises]
    )

    RequestConfig(request).configure(table)
    return render(request, "dashboard/performance_details.html", {
        "table": table
    })
