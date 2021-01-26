from copy import copy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
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
    course_author = request.user

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, "dashboard/courses-list.html", {
        "table": table,
        "course_author": course_author
    })


@login_required
def course_add_view(request):
    context = {
        'verbose_name': Course._meta.verbose_name,
        'verbose_name_plural': Course._meta.verbose_name_plural,
    }

    if request.method == 'POST':
        form = DashboardCourseForm(data=request.POST)
        form.context = {'user': request.user}
        if form.is_valid():
            course = form.save(commit=False)
            course.authored_by = request.user
            course.save()
            if 'save-and-continue' in request.POST:
                success_url = reverse('dashboard:edit-course',
                                      kwargs={'course_name': course.title})
                messages.add_message(request, messages.SUCCESS,
                                     f"{context['verbose_name']} has been saved successfully.")
            else:
                success_url = reverse('dashboard:courses-list')
            return redirect(success_url)
        context['form'] = form
        return render(request, "dashboard/content.html", context)
    else:
        form = DashboardCourseForm(initial=request.session.get('clone_data'))
        request.session['clone_data'] = None

    context['form'] = form
    return render(request, "dashboard/content.html", context)


@login_required
def course_edit_view(request, course_name):
    course = get_object_or_404(Course, title=course_name)

    if request.user != course.authored_by:
        raise PermissionDenied

    context = {
        'verbose_name': course._meta.verbose_name,
        'verbose_name_plural': course._meta.verbose_name_plural,
        'has_been_performed': course.has_been_performed,
        'redirect_url': reverse('dashboard:courses-list')
    }

    if request.method == 'POST':
        form = DashboardCourseForm(data=request.POST, instance=course)
        form.context = {'user': request.user}
        if form.is_valid():
            if 'duplicate' in request.POST:
                unique_fields = Course.get_unique_fields()
                clone_data = copy(form.cleaned_data)
                for field in clone_data:
                    if field in unique_fields:
                        clone_data[field] = None
                request.session['clone_data'] = clone_data
                return redirect('dashboard:add-course')

            course = form.save(commit=False)
            course.authored_by = request.user
            course.save()
            if 'save-and-continue' in request.POST:
                success_url = reverse('dashboard:edit-course',
                                      kwargs={'course_name': course.title})
                messages.add_message(request, messages.SUCCESS,
                                     f"{context['verbose_name']} has been saved successfully.")
            else:
                success_url = reverse('dashboard:courses-list')
            return redirect(success_url)
        context['form'] = form
        return render(request, "dashboard/content.html", context)

    form = DashboardCourseForm(instance=course)

    context['form'] = form
    return render(request, "dashboard/content.html", context)


@login_required
def course_delete_view(request, course_name):
    course = get_object_or_404(Course, title=course_name)

    if request.user != course.authored_by:
        raise PermissionDenied

    if course.authored_by != request.user:
        raise PermissionDenied
    if request.method == 'POST':
        course.delete()
        return redirect('dashboard:courses-list')

    context = {'obj': course, 'obj_name': course.title,
               'verbose_name': course._meta.verbose_name,
               'verbose_name_plural': course._meta.verbose_name_plural,
               'has_been_performed': course.has_been_performed,
               'redirect_url': reverse('dashboard:courses-list')}
    return render(request, 'dashboard/delete-confirmation.html', context)
