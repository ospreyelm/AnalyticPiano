from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import RequestConfig

from apps.dashboard.forms import AddSupervisorForm, AddSubscriberForm, RemoveSubscriptionConfirmationForm
from apps.dashboard.tables import SupervisorsTable, SubscribersTable, CoursesListTable, SupervisorsCoursesListTable
from apps.dashboard.views.performance import User
from apps.exercises.models import Course


@login_required
def supervisors_view(request):
    visible_supervisors = [x for x in request.user.supervisors]
    approved_supervisors = [x for x in request.user.supervisors if request.user.is_subscribed_to(x)]

    supervisors_table = SupervisorsTable([{"supervisor": x, "user": request.user} for x in visible_supervisors])
    RequestConfig(request).configure(supervisors_table)

    if request.method == 'POST':
        supervisor_email = request.POST.get('email').lower()
        form = AddSupervisorForm(data={'email': supervisor_email})
        form.context = {'user': request.user}

        if form.is_valid():
            supervisor = get_object_or_404(User, email=form.cleaned_data['email'])
            request.user.subscribe_to(supervisor, status=User.SUPERVISOR_STATUS_SUBSCRIPTION_WAIT)
            return redirect('dashboard:subscriptions')
        return render(request, "dashboard/subscriptions.html", {
            "form": form, "table": supervisors_table, "courses_table": supervisors_courses_table
        })
    else:
        form = AddSupervisorForm()

    return render(request, "dashboard/subscriptions.html", {
        "form": form,
        "table": supervisors_table
    })


@login_required
def supervisors_courses_view(request):
    visible_supervisors = [x for x in request.user.supervisors]
    approved_supervisors = [x for x in request.user.supervisors if request.user.is_subscribed_to(x)]

    supervisors_courses = Course.objects.filter(
        Q(visible_to___members__contains=[request.user.id]) | Q(visible_to=None),
        authored_by__in=approved_supervisors,
    ).distinct()
    supervisors_courses_table = SupervisorsCoursesListTable(supervisors_courses)
    RequestConfig(request).configure(supervisors_courses_table)

    return render(request, "dashboard/subscriptions.html", {
        "courses_table": supervisors_courses_table
    })


@login_required
def subscribers_view(request):
    subscribers_table = SubscribersTable([{"subscriber": x, "user": request.user} for x in request.user.subscribers])
    RequestConfig(request).configure(subscribers_table)

    if request.method == 'POST':
        form = AddSubscriberForm(data={'email': request.POST.get('email').lower()})
        form.context = {'user': request.user}
        if form.is_valid():
            subscriber = get_object_or_404(User, email=form.cleaned_data['email'])
            subscriber.subscribe_to(request.user, status=User.SUPERVISOR_STATUS_INVITATION_WAIT)
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
def unsubscribe_confirmation(request, supervisor_id):
    supervisor = get_object_or_404(User, id=supervisor_id)

    context = {
        'email': supervisor.email,
        'redirect_url': reverse('dashboard:subscriptions')
    }

    if request.method == 'POST':
        form = RemoveSubscriptionConfirmationForm(request.POST)
        form.context = {'email': supervisor.email}
        if form.is_valid():
            return redirect('dashboard:unsubscribe', supervisor_id=supervisor_id)
        return render(request, "dashboard/remove-subscription-confirmation.html",
                      context={"form": form, **context})
    form = RemoveSubscriptionConfirmationForm()
    return render(request, "dashboard/remove-subscription-confirmation.html",
                  context={"form": form, **context})


@login_required
def unsubscribe_view(request, supervisor_id):
    supervisor = get_object_or_404(User, id=supervisor_id)
    request.user.unsubscribe_from(supervisor)
    return redirect('dashboard:subscriptions')


@login_required
def remove_subscriber_confirmation(request, subscriber_id):
    subscriber = get_object_or_404(User, id=subscriber_id)

    context = {
        'email': subscriber.email,
        'redirect_url': reverse('dashboard:subscribers')
    }

    if request.method == 'POST':
        form = RemoveSubscriptionConfirmationForm(request.POST)
        form.context = {'email': subscriber.email}
        if form.is_valid():
            return redirect('dashboard:remove-subscriber', subscriber_id=subscriber_id)
        return render(request, "dashboard/remove-subscription-confirmation.html",
                      context={"form": form, **context})
    form = RemoveSubscriptionConfirmationForm()
    return render(request, "dashboard/remove-subscription-confirmation.html",
                  context={"form": form, **context})


@login_required
def remove_subscriber_view(request, subscriber_id):
    subscriber = get_object_or_404(User, id=subscriber_id)
    subscriber.unsubscribe_from(request.user)
    return redirect('dashboard:subscribers')


@login_required
def accept_subscription_view(request, supervisor_id, subscriber_id):
    subscriber = get_object_or_404(User, id=subscriber_id)
    supervisor = get_object_or_404(User, id=supervisor_id)
    supervisor.accept_subscription(supervisor, subscriber)
    return redirect(request.META['HTTP_REFERER'])


@login_required
def decline_subscription_view(request, supervisor_id, subscriber_id):
    subscriber = get_object_or_404(User, id=subscriber_id)
    supervisor = get_object_or_404(User, id=supervisor_id)
    supervisor.decline_subscription(supervisor, subscriber)
    return redirect(request.META['HTTP_REFERER'])
