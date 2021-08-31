from copy import copy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_tables2 import RequestConfig, Column

from apps.dashboard.forms import DashboardCourseForm
from apps.dashboard.tables import CoursesListTable, CourseActivityTable
from apps.exercises.models import Course, PerformanceData


@login_required
def courses_list_view(request):
    courses = Course.objects.filter(
        authored_by=request.user
    ).select_related('authored_by')

    table = CoursesListTable(courses)
    course_author = request.user

    RequestConfig(request, paginate={"per_page": 50}).configure(table)
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

    if request.method == 'POST':
        course.delete()
        return redirect('dashboard:courses-list')

    context = {'obj': course, 'obj_name': course.title,
               'verbose_name': course._meta.verbose_name,
               'verbose_name_plural': course._meta.verbose_name_plural,
               'has_been_performed': course.has_been_performed,
               'redirect_url': reverse('dashboard:courses-list')}
    return render(request, 'dashboard/delete-confirmation.html', context)


@login_required
def course_activity_view(request, course_name):
    course = get_object_or_404(Course, title=course_name)

    if request.user != course.authored_by:
        raise PermissionDenied

    subscribers = request.user.subscribers

    data = []

    JOIN_STR = ' '
    PLAYLISTS = course.playlists.split(JOIN_STR)
    course_performances = PerformanceData.objects.filter(
        playlist__id__in=PLAYLISTS, user__in=subscribers
    ).select_related('user', 'playlist')

    # In the course activity table, only show the subscribers who have performed at least one playlist from the course
    performers = subscribers.filter(id__in=list(course_performances.values_list('user', flat=True)))
    for performer in performers:
        user_performances = course_performances.filter(user=performer)
        user_data = {
            'subscriber_email': performer.email,
            'subscriber_name': performer.get_full_name(),
        }
        for idx in range(len(PLAYLISTS)):
            ## FIXME: inefficient
            playlist = course.playlist_objects.filter(id=PLAYLISTS[idx]).first()
            playlist_performance = user_performances.filter(playlist=playlist).last()
            if playlist_performance:
                user_data[idx] = mark_safe(
                    f'<span class="{str(playlist_performance.playlist_passed).lower()}">✘</span>'
                    # f'<br>'
                    # f'{playlist_performance.playlist_pass_date if playlist_performance.playlist_pass_date else ""}'
                )
            else:
                user_data[idx] = playlist_performance.playlist_passed if playlist_performance else ''

        data.append(user_data)

    table = CourseActivityTable(
        data=data,
        extra_columns=[(str(idx), Column(verbose_name=str(idx+1),
                                               orderable=True))
                       for idx in range(len(course.playlist_objects))]
    )

    RequestConfig(request).configure(table)
    return render(request, "dashboard/course-activity.html", {
        "table": table,
        "course_name": course_name
    })
