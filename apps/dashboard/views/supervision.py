from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django_tables2 import RequestConfig

from apps.dashboard.forms import AddSupervisorForm, AddSubscriberForm
from apps.dashboard.tables import SupervisorsTable, SubscribersTable
from apps.dashboard.views.performance import User


@login_required
def supervisors_view(request):
    supervisors_table = SupervisorsTable([{"supervisor": x} for x in request.user.supervisors])
    RequestConfig(request).configure(supervisors_table)

    if request.method == 'POST':
        supervisor_email = request.POST.get('email')
        form = AddSupervisorForm(data={'email': supervisor_email})
        form.context = {'user': request.user}

        if form.is_valid():
            supervisor = get_object_or_404(User, email=form.cleaned_data['email'])
            request.user.subscribe_to(supervisor)
            return redirect('dashboard:subscriptions')
        return render(request, "dashboard/subscriptions.html", {
            "form": form, "table": supervisors_table
        })
    else:
        form = AddSupervisorForm()

    return render(request, "dashboard/subscriptions.html", {
        "form": form,
        "table": supervisors_table,
    })


@login_required
def subscribers_view(request):
    subscribers_table = SubscribersTable([{"subscriber": x} for x in request.user.subscribers])
    RequestConfig(request).configure(subscribers_table)

    if request.method == 'POST':
        form = AddSubscriberForm(data={'email': request.POST.get('email')})
        form.context = {'user': request.user}
        if form.is_valid():
            subscriber = get_object_or_404(User, email=form.cleaned_data['email'])
            subscriber.subscribe_to(request.user)
            return redirect('dashboard:subscribers')
        return render(request, "dashboard/subscribers.html", {
            "form": form, "table": subscribers_table
        })
    else:
        form = AddSubscriberForm()

    return render(request, "dashboard/subscribers.html", {
        "form": form, "table": subscribers_table
    })


@login_required
def unsubscribe_view(request, supervisor_id):
    supervisor = get_object_or_404(User, id=supervisor_id)
    request.user.unsubscribe_from(supervisor)
    return redirect('dashboard:subscriptions')


@login_required
def remove_subscriber_view(request, subscriber_id):
    subscriber = get_object_or_404(User, id=subscriber_id)
    subscriber.unsubscribe_from(request.user)
    return redirect('dashboard:subscribers')
