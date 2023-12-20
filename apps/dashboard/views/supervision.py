from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import RequestConfig

from apps.dashboard.forms import (
    AddSupervisorForm,
    AddSubscriberForm,
    AddConnectionForm,
    RemoveSubscriptionConfirmationForm,
    RemoveConnectionConfirmationForm,
)
from apps.dashboard.tables import (
    SupervisorsTable,
    SubscribersTable,
    ConnectionsTable,
    CoursesListTable,
    AvailableCoursesTable,
)
from apps.dashboard.views.performance import User
from apps.exercises.models import Course


@login_required
def supervisors_courses_view(request):
    visible_users = request.user.content_permits

    visible_courses = Course.objects.filter(
        Q(visible_to__members__id__contains=request.user.id) | Q(open=True),
        authored_by__in=visible_users,
    ).distinct()

    visible_course_table = AvailableCoursesTable(visible_courses)
    RequestConfig(request).configure(visible_course_table)

    return render(
        request,
        "dashboard/subscriptions-courses.html",
        {"courses_table": visible_course_table},
    )


@login_required
def unsubscribe_confirmation(request, supervisor_id):
    supervisor = get_object_or_404(User, id=supervisor_id)

    context = {
        "email": supervisor.email,
        "redirect_url": reverse("dashboard:subscriptions"),
    }

    if request.method == "POST":
        form = RemoveSubscriptionConfirmationForm(request.POST)
        form.context = {"email": supervisor.email}
        if form.is_valid():
            return redirect("dashboard:unsubscribe", supervisor_id=supervisor_id)
        return render(
            request,
            "dashboard/remove-subscription-confirmation.html",
            context={"form": form, **context},
        )
    form = RemoveSubscriptionConfirmationForm()
    return render(
        request,
        "dashboard/remove-subscription-confirmation.html",
        context={"form": form, **context},
    )


@login_required
def remove_subscriber_confirmation(request, subscriber_id):
    subscriber = get_object_or_404(User, id=subscriber_id)

    context = {
        "email": subscriber.email,
        "redirect_url": reverse("dashboard:subscribers"),
    }

    if request.method == "POST":
        form = RemoveSubscriptionConfirmationForm(request.POST)
        form.context = {"email": subscriber.email}
        if form.is_valid():
            return redirect("dashboard:remove-subscriber", subscriber_id=subscriber_id)
        return render(
            request,
            "dashboard/remove-subscription-confirmation.html",
            context={"form": form, **context},
        )
    form = RemoveSubscriptionConfirmationForm()
    return render(
        request,
        "dashboard/remove-subscription-confirmation.html",
        context={"form": form, **context},
    )


@login_required
def connections_view(request):  # exact copy of subscribers table with renamed variables
    connections_table = ConnectionsTable(
        [{"other": x, "user": request.user} for x in request.user.connections],
    )
    RequestConfig(request).configure(connections_table)

    if request.method == "POST":
        form = AddConnectionForm(data={"email": request.POST.get("email").lower()})
        form.context = {"user": request.user}
        if form.is_valid():
            other = get_object_or_404(User, email=form.cleaned_data["email"])
            request.user.pin_connection(other)
            return redirect("dashboard:connections")
        return render(
            request,
            "dashboard/connections.html",
            {"form": form, "table": connections_table},
        )
    else:
        form = AddConnectionForm()

    return render(
        request,
        "dashboard/connections.html",
        {"form": form, "table": connections_table},
    )


@login_required
def toggle_content_permit_view(request, other_id):
    other = get_object_or_404(User, id=other_id)
    request.user.toggle_content_permit(other)
    return redirect(request.META["HTTP_REFERER"])


@login_required
def toggle_performance_permit_view(request, other_id):
    other = get_object_or_404(User, id=other_id)
    request.user.toggle_performance_permit(other)
    return redirect(request.META["HTTP_REFERER"])


@login_required
def toggle_connection_pin_view(request, other_id):
    other = get_object_or_404(User, id=other_id)
    request.user.toggle_connection_pin(other)
    return redirect("dashboard:connections")


@login_required
def toggle_connection_pin_with_confirmation(request, other_id):
    connection = get_object_or_404(User, id=other_id)

    context = {
        "email": connection.email,
        "redirect_url": reverse("dashboard:connections"),
    }

    if request.method == "POST":
        form = RemoveConnectionConfirmationForm(request.POST)
        form.context = {"email": connection.email}
        if form.is_valid():
            return redirect("dashboard:toggle-connection-pin", other_id=other_id)
        return render(
            request,
            "dashboard/toggle-connection-pin-with-confirmation.html",
            context={"form": form, **context},
        )
    form = RemoveConnectionConfirmationForm()
    return render(
        request,
        "dashboard/toggle-connection-pin-with-confirmation.html",
        context={"form": form, **context},
    )
