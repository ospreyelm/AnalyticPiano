from copy import copy
import datetime

from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.safestring import mark_safe
from apps.dashboard.views.m2m_view import handle_m2m
from django_tables2 import RequestConfig, Column

from apps.dashboard.filters import CourseActivityGroupsFilter
from apps.dashboard.forms import DashboardCourseForm
from apps.dashboard.tables import CoursesListTable, CourseActivityTable
from apps.exercises.models import (
    Course,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
)
from apps.accounts.models import Group


@login_required
def courses_list_view(request):
    courses = Course.objects.filter(authored_by=request.user).select_related(
        "authored_by"
    )

    table = CoursesListTable(courses)
    courses_author = request.user

    RequestConfig(request, paginate={"per_page": 50}).configure(table)
    return render(
        request,
        "dashboard/courses-list.html",
        {"table": table, "courses_author": courses_author},
    )


@login_required
def course_add_view(request):
    context = {
        "verbose_name": Course._meta.verbose_name,
        "verbose_name_plural": Course._meta.verbose_name_plural,
    }

    if request.method == "POST":
        form = DashboardCourseForm(data=request.POST, user=request.user)
        form.context = {"user": request.user}
        if form.is_valid():

            course = form.save(commit=False)
            course.authored_by = request.user
            course.save()

            form.save_m2m()

            if "save-and-continue" in request.POST:
                success_url = reverse(
                    "dashboard:edit-course", kwargs={"course_id": course.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been saved successfully.",
                )
            else:
                success_url = reverse("dashboard:courses-list")
            return redirect(success_url)
        context["form"] = form
        return render(request, "dashboard/content.html", context)
    else:
        form = DashboardCourseForm(
            initial=request.session.get("clone_data"), user=request.user
        )
        request.session["clone_data"] = None

    context["form"] = form
    return render(request, "dashboard/content.html", context)


@login_required
def course_edit_view(request, course_id):
    def parse_group(group):
        return {
            "name": group.name,
            "id": group.id,
            "url_id": group.id if group.manager_id == request.user.id else None,
        }

    def parse_pco(pco):
        playlist = pco.playlist
        return {
            "name": playlist.name,
            "id": playlist._id,
            "order": pco.order,
            "through_id": pco._id,
            "due_date": pco.due_date,
            "publish_date": pco.publish_date,
            "url_id": playlist.id
            if playlist.authored_by_id == request.user.id
            else None,
        }

    course = get_object_or_404(Course, id=course_id)

    if request.user != course.authored_by:
        raise PermissionDenied

    playlists_list = list(
        map(parse_pco, PlaylistCourseOrdered.objects.filter(course_id=course._id))
    )
    playlists_list.sort(key=lambda pco: pco["order"])

    groups_list = list(map(parse_group, course.visible_to.all()))

    playlists_options = list(
        filter(
            lambda p: p not in course.playlists.all(),
            Playlist.objects.filter(
                Q(authored_by_id=request.user.id) | Q(is_public=True)
            ),
        )
    )

    playlists_options.sort(
        key=lambda p: p.authored_by_id if (p.authored_by_id != request.user.id) else -1
    )

    context = {
        "verbose_name": course._meta.verbose_name,
        "verbose_name_plural": course._meta.verbose_name_plural,
        "has_been_performed": course.has_been_performed,
        "redirect_url": reverse("dashboard:courses-list"),
        "editing": True,
        "m2m_added": {
            "playlists": playlists_list,
            "visible_to": groups_list,
        },
        "m2m_options": {
            "playlists": playlists_options,
            "visible_to": list(
                filter(
                    lambda g: g not in course.visible_to.all(),
                    Group.objects.filter(manager_id=course.authored_by_id),
                ),
            ),
        },
        "user": request.user,
    }

    if request.method == "POST":
        form = DashboardCourseForm(
            data=request.POST, instance=course, user=request.user
        )
        if form.is_valid():
            course = form.save(commit=False)
            added_playlist_id = request.POST.get("playlists_add")
            if added_playlist_id != "":
                course.playlists.add(
                    Playlist.objects.filter(id=added_playlist_id).first(),
                    through_defaults={"order": len(course.playlists.all())},
                )
            added_group_id = request.POST.get("visible_to_add")
            if added_group_id != "":
                course.visible_to.add(Group.objects.filter(id=added_group_id).first())
            due_dates = request.POST.getlist("playlists_due_date")
            publish_dates = request.POST.getlist("playlists_publish_date")
            for i in range(0, len(playlists_list)):
                current_pco = PlaylistCourseOrdered.objects.filter(
                    _id=playlists_list[i]["through_id"]
                ).first()
                if due_dates[i] != "":
                    current_pco.due_date = datetime.datetime.strptime(
                        due_dates[i], "%Y-%m-%dT%M:%S"
                    )
                if publish_dates[i] != "":
                    current_pco.publish_date = datetime.datetime.strptime(
                        publish_dates[i], "%Y-%m-%dT%M:%S"
                    )
                current_pco.save()
            handle_m2m(
                request,
                "playlists",
                {"course_id": course._id},
                "playlist_id",
                list(
                    map(
                        lambda p: Playlist.objects.filter(_id=p["id"]).first(),
                        playlists_list,
                    )
                ),
                ThroughModel=PlaylistCourseOrdered,
            )
            handle_m2m(
                request,
                "visible_to",
                {"course_id": course._id},
                "group_id",
                list(
                    map(
                        lambda g: Group.objects.filter(id=g["id"]).first(),
                        groups_list,
                    )
                ),
                parent_instance=course,
                ChildModel=Group,
            )
            course.authored_by = request.user
            course.save()

            if "save-and-continue" in request.POST:
                success_url = reverse(
                    "dashboard:edit-course", kwargs={"course_id": course.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been saved successfully.",
                )
            elif "duplicate" in request.POST:
                visible_to_groups = course.visible_to.all()
                pcos = PlaylistCourseOrdered.objects.filter(course_id=course._id)
                course.pk = None
                course.id = None
                course.title += " (Copy)"
                course.save()
                for group in visible_to_groups:
                    course.visible_to.add(group)
                for pco in pcos:
                    playlist_to_add = Playlist.objects.filter(
                        _id=pco.playlist_id
                    ).first()
                    course.playlists.add(
                        playlist_to_add,
                        through_defaults={
                            "order": pco.order,
                            "due_date": pco.due_date,
                            "publish_date": pco.publish_date,
                        },
                    )
                return redirect("dashboard:edit-course", course.id)
            else:
                success_url = reverse("dashboard:courses-list")

            return redirect(success_url)
        context["form"] = form
        return render(request, "dashboard/content.html", context)

    form = DashboardCourseForm(instance=course, user=request.user)

    context["form"] = form
    return render(request, "dashboard/content.html", context)


@login_required
def course_delete_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user != course.authored_by:
        raise PermissionDenied

    if request.method == "POST":
        course.delete()
        return redirect("dashboard:courses-list")

    context = {
        "obj": course,
        "obj_name": course.title,
        "verbose_name": course._meta.verbose_name,
        "verbose_name_plural": course._meta.verbose_name_plural,
        "has_been_performed": course.has_been_performed,
        "redirect_url": reverse("dashboard:courses-list"),
    }
    return render(request, "dashboard/delete-confirmation.html", context)


@login_required
def course_activity_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user != course.authored_by:
        raise PermissionDenied

    subscribers = request.user.subscribers

    data = []

    JOIN_STR = " "
    PLAYLISTS = course.playlists.split(JOIN_STR)
    course_performances = PerformanceData.objects.filter(
        playlist__id__in=PLAYLISTS, user__in=subscribers
    ).select_related("user", "playlist")

    if course.due_dates:
        due_dates = {
            playlist: course.get_due_date(playlist) for playlist in course.playlists
        }

    performance_data = {}
    for performance in course_performances:
        performer = performance.user
        performance_data[performer] = performance_data.get(performer, {})

        playlist_num = PLAYLISTS.index(performance.playlist.id)

        pass_mark = (
            f'<span class="true">P</span>' if performance.playlist_passed else ""
        )  # Pass

        if course.due_dates and performance.playlist_passed:
            pass_date = performance.get_local_pass_date()
            playlist_due_date = due_dates.get(performance.playlist)
            if playlist_due_date < pass_date:
                diff = pass_date - playlist_due_date
                days, seconds = diff.days, diff.seconds
                hours = days * 24 + seconds // 3600

                if hours >= 6:
                    pass_mark = (
                        '<span class="true due-date-hours-exceed">T</span>'  # Tardy
                    )

                if days >= 7:
                    pass_mark = (
                        '<span class="true due-date-days-exceed">L</span>'  # Late
                    )

        performance_data[performer].setdefault(playlist_num, mark_safe(pass_mark))

    for performer, playlists in performance_data.items():
        [
            performance_data[performer].setdefault(idx, "")
            for idx in range(len(PLAYLISTS))
        ]
        data.append(
            {
                "subscriber": performer,
                "subscriber_name": performer.get_full_name(),
                "groups": [],
                **playlists,
            }
        )

    filters = CourseActivityGroupsFilter(
        queryset=course.visible_to.all(), data=request.GET
    )
    filters.form.is_valid()
    filtered_groups = filters.form.cleaned_data["groups"]

    if filtered_groups:
        groups = Group.objects.filter(id__in=list(map(int, filtered_groups)))

        # separate performers by the filtered groups
        for group in groups:
            for performance in data:
                if performance["subscriber"] in group.members:
                    performance["groups"].append(group.name)

        for performance in data:
            performance["groups"] = ", ".join(performance["groups"])

            # remove performers who are not members of the filtered groups
            if not performance["groups"]:
                data.pop(data.index(performance))

    table = CourseActivityTable(
        data=data,
        extra_columns=[
            (str(idx), Column(verbose_name=str(idx + 1), orderable=True))
            for idx in range(len(course.playlists))
        ],
    )

    if not filtered_groups:
        table.exclude = ("groups",)

    RequestConfig(request, paginate={"per_page": 35}).configure(table)
    return render(
        request,
        "dashboard/course-activity.html",
        {"table": table, "course_id": course_id, "filters": filters},
    )
