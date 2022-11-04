from copy import copy
import datetime

from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import cache_page
from apps.dashboard.views.m2m_view import handle_m2m
from django_tables2 import RequestConfig, Column

from apps.dashboard.filters import CourseActivityGroupsFilter
from apps.dashboard.forms import DashboardCourseForm
from apps.dashboard.tables import (
    CoursesListTable,
    CourseActivityTable,
    PlaylistActivityColumn,
)
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
        key=lambda p: (
            p.authored_by_id if (p.authored_by_id != request.user.id) else -1,
            p.name,
        )
    )

    groups_options = list(
        filter(
            lambda g: g not in course.visible_to.all(),
            list(Group.objects.filter(manager_id=course.authored_by_id)),
        )
    )

    groups_options.sort(key=lambda g: g.name)

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
        "m2m_options": {"playlists": playlists_options, "visible_to": groups_options},
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
                    Playlist.objects.get(id=added_playlist_id),
                    through_defaults={"order": len(course.playlists.all())},
                )
            added_group_id = request.POST.get("visible_to_add")
            if added_group_id != "":
                course.visible_to.add(Group.objects.get(id=added_group_id))
            due_dates = request.POST.getlist("playlists_due_date")
            publish_dates = request.POST.getlist("playlists_publish_date")
            for i in range(0, len(playlists_list)):
                current_pco = PlaylistCourseOrdered.objects.get(
                    _id=playlists_list[i]["through_id"]
                )
                if due_dates[i] != "":
                    current_pco.due_date = datetime.datetime.strptime(
                        due_dates[i], "%Y-%m-%d"
                    )
                if publish_dates[i] != "":
                    current_pco.publish_date = datetime.datetime.strptime(
                        publish_dates[i], "%Y-%m-%d"
                    )
                current_pco.save()
            handle_m2m(
                request,
                "playlists",
                {"course_id": course._id},
                "playlist_id",
                list(
                    map(
                        lambda p: Playlist.objects.get(_id=p["id"]),
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
                        lambda g: Group.objects.get(id=g["id"]),
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
                    playlist_to_add = Playlist.objects.filter(_id=pco.playlist_id).get()
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
# @cache_page(60 * 15)
def course_activity_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user != course.authored_by:
        raise PermissionDenied

    # Change this to alter the number of displayed subscribers per page.
    subscribers_per_page = 35

    filters = CourseActivityGroupsFilter(
        queryset=course.visible_to.all(), data=request.GET
    )
    filters.form.is_valid()
    curr_group_ids = [int(g) for g in filters.form.cleaned_data["groups"] or []]
    curr_groups = Group.objects.filter(id__in=curr_group_ids)

    subscribers = request.user.subscribers
    if len(curr_group_ids) > 0:
        subscribers = subscribers.filter(participant_groups__id__in=curr_group_ids)
    course_playlists = list(
        PlaylistCourseOrdered.objects.filter(course=course)
        .order_by("order")
        .select_related("playlist")
    )
    playlists = list(map(lambda pco: pco.playlist, course_playlists))

    performance_dict = course.performance_dict
    data = {
        performer: {
            "subscriber": performer,
            "subscriber_name": performer.get_full_name(),
            "groups": ", ".join(
                [
                    str(g)
                    for g in curr_groups.intersection(
                        performer.participant_groups.all()
                    )
                ]
            ),
            **performance_dict.get(str(performer), {}),
        }
        for performer in subscribers
    }

    table = CourseActivityTable(
        data=data.values(),
        extra_columns=[
            (
                str(idx),
                PlaylistActivityColumn(verbose_name=str(idx + 1), orderable=True),
            )
            for idx in range(len(playlists))
        ],
    )

    if len(curr_group_ids) == 0:
        table.exclude = ("groups",)

    RequestConfig(request, paginate={"per_page": subscribers_per_page}).configure(table)

    return render(
        request,
        "dashboard/course-activity.html",
        {"table": table, "course_id": course_id, "filters": filters},
    )
