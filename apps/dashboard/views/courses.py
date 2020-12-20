from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django_tables2 import RequestConfig

from apps.dashboard.forms import DashboardCourseForm
from apps.dashboard.tables import CoursesListTable
from apps.exercises.models import Course


@login_required
def courses_list_view(request):
    courses = Course.objects.filter(
        authored_by=request.user
    ).select_related('authored_by')

    table = CoursesListTable(courses)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, "dashboard/courses-list.html", {
        "table": table,
    })


@login_required
def course_add_view(request):
    if request.method == 'POST':
        form = DashboardCourseForm(data=request.POST)
        form.context = {'user': request.user}
        if form.is_valid():
            course = form.save(commit=False)
            course.authored_by = request.user
            course.save()
            return redirect('dashboard:courses-list')
    else:
        form = DashboardCourseForm()

    return render(request, "dashboard/course.html", {
        "form": form
    })


@login_required
def course_edit_view(request, course_name):
    course = get_object_or_404(Course, title=course_name)

    if request.method == 'POST':
        form = DashboardCourseForm(data=request.POST, instance=course)
        form.context = {'user': request.user}
        if form.is_valid():
            course = form.save(commit=False)
            course.authored_by = request.user
            course.save()
            return redirect('dashboard:courses-list')
    else:
        form = DashboardCourseForm(instance=course)

    return render(request, "dashboard/course.html", {
        "form": form
    })


@login_required
def course_delete_view(request, course_name):
    course = get_object_or_404(Course, name=course_name)
    if course.authored_by != request.user:
        raise PermissionDenied

    if course.has_been_performed:
        raise ValidationError('Courses that have been performed cannot be deleted.')

    course.delete()
    return redirect('dashboard:courses-list')
