from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import RequestConfig

from apps.dashboard.forms import (
    AddConnectionForm,
    RemoveConnectionConfirmationForm,
)
from apps.dashboard.tables import (
    ConnectionsTable,
    CoursesListTable,
    CoursesByOthersTable,
)
from apps.dashboard.views.performance import User
from apps.exercises.models import Course


@login_required
def courses_by_others_view(request):
    visible_users = request.user.content_permits

    visible_courses = Course.objects.filter(
        Q(visible_to__members__id__contains=request.user.id) | Q(open=True),
        authored_by__in=visible_users,
    ).distinct()

    visible_course_table = CoursesByOthersTable(visible_courses)
    RequestConfig(request).configure(visible_course_table)

    return render(
        request,
        "dashboard/courses-by-others.html",
        {"courses_table": visible_course_table},
    )


@login_required
def connections_view(request):
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
