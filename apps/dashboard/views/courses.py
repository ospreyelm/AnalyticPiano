from copy import copy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_tables2 import RequestConfig, Column

from apps.dashboard.filters import CourseActivityGroupsFilter
from apps.dashboard.forms import DashboardCourseForm
from apps.dashboard.tables import CoursesListTable, CourseActivityTable
from apps.exercises.models import Course, PerformanceData
from apps.accounts.models import Group


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
        form = DashboardCourseForm(data=request.POST, user=request.user)
        form.context = {'user': request.user}
        if form.is_valid():
            course = form.save(commit=False)
            course.authored_by = request.user
            course.save()

            form.save_m2m()

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
        form = DashboardCourseForm(initial=request.session.get('clone_data'), user=request.user)
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
        form = DashboardCourseForm(data=request.POST, instance=course, user=request.user)
        form.context = {'user': request.user}
        if form.is_valid():
            if 'duplicate' in request.POST:
                unique_fields = Course.get_unique_fields()
                clone_data = copy(form.cleaned_data)
                clone_data['visible_to'] = list(form.cleaned_data.pop('visible_to').values_list('id', flat=True))
                for field in clone_data:
                    if field in unique_fields:
                        clone_data[field] = None
                request.session['clone_data'] = clone_data
                return redirect('dashboard:add-course')

            course = form.save(commit=False)
            course.authored_by = request.user
            course.save()

            form.save_m2m()

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

    form = DashboardCourseForm(instance=course, user=request.user)

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

    if course.due_dates:
        due_dates = {playlist: course.get_due_date(playlist)
                     for playlist in course.playlist_objects}

    performance_data = {}
    for performance in course_performances:
        performer = performance.user
        performance_data[performer] = performance_data.get(performer, {})

        playlist_num = PLAYLISTS.index(performance.playlist.id)

        pass_mark = f'<span class="true">✘</span>' if performance.playlist_passed else ''

        if course.due_dates and performance.playlist_passed:
            pass_date = performance.get_local_pass_date()
            playlist_due_date = due_dates.get(performance.playlist)
            if playlist_due_date < pass_date:
                diff = pass_date - playlist_due_date
                days, seconds = diff.days, diff.seconds
                hours = days * 24 + seconds // 3600

                if hours >= 6:
                    pass_mark = '<span class="true due-date-hours-exceed">✘</span>'

                if days >= 7:
                    pass_mark = '<span class="true due-date-days-exceed">✘</span>'

        performance_data[performer].setdefault(
            playlist_num, mark_safe(pass_mark)
        )

    for performer, playlists in performance_data.items():
        [performance_data[performer].setdefault(idx, '') for idx in range(len(PLAYLISTS))]
        data.append({'subscriber': performer,
                     'subscriber_name': performer.get_full_name(),
                     'groups': [], **playlists})

    filters = CourseActivityGroupsFilter(
        queryset=course.visible_to.all(), data=request.GET
    )
    filters.form.is_valid()
    filtered_groups = filters.form.cleaned_data['groups']

    if filtered_groups:
        groups = Group.objects.filter(id__in=list(map(int, filtered_groups)))

        # separate performers by the filtered groups
        for group in groups:
            for performance in data:
                if performance['subscriber'].id in group._members:
                    performance['groups'].append(group.name)

        for performance in data:
            performance['groups'] = ', '.join(performance['groups'])

            # remove performers who are not members of the filtered groups
            if not performance['groups']:
                data.pop(data.index(performance))

    table = CourseActivityTable(
        data=data,
        extra_columns=[(str(idx), Column(verbose_name=str(idx + 1),
                                         orderable=True))
                       for idx in range(len(course.playlist_objects))]
    )

    if not filtered_groups:
        table.exclude = ('groups',)

    RequestConfig(request, paginate={"per_page": 35}).configure(table)
    return render(request, "dashboard/course-activity.html", {
        "table": table,
        "course_name": course_name,
        "filters": filters
    })
