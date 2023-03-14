from copy import copy
import datetime
import pytz
import re
import math

from django.db.models import Q
from django.conf import settings
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
            "1" + str(p.authored_by_id)
            if (p.authored_by_id != request.user.id)
            else "0",
            p.name if (p.authored_by_id != request.user.id) else -p._id,
        ),
        reverse=False,
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
                    through_defaults={"order": len(course.playlists.all()) + 1},
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
                    ).astimezone(pytz.timezone(settings.TIME_ZONE))
                    # due dates are input here by course authors and should be interpreted
                    # as 23:59:59 in terms of their own or their institution's timezone
                    current_pco.due_date = current_pco.due_date.replace(
                        hour=23, minute=59, second=59
                    )
                if publish_dates[i] != "":
                    current_pco.publish_date = datetime.datetime.strptime(
                        publish_dates[i], "%Y-%m-%d"
                    ).astimezone(pytz.timezone(settings.TIME_ZONE))
                    # publish dates are input here by course authors and should be interpreted
                    # as 00:00:00 in terms of their own or their institution's timezone
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
            elif "duplicate" in request.POST and False:
                visible_to_groups = course.visible_to.all()
                pcos = PlaylistCourseOrdered.objects.filter(course_id=course._id)
                course.pk = None
                course.id = None
                course.performance_dict = {}
                course.title = (
                    course.title[0:57] + " (copy)"
                )  # account for max_length of course.title
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


def playlist_column_verbose_name(playlist_id, course):
    playlist = Playlist.objects.filter(id=playlist_id).first()
    if playlist != None:
        pco = PlaylistCourseOrdered.objects.filter(
            Q(playlist_id=playlist._id) & Q(course_id=course._id)
        )
        if len(pco) > 0:
            return "#" + str(pco.first().order)
    return playlist_id


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
            "subscriber": performer,  # n.b. not a string!
            "subscriber_name": performer.get_full_name(),
            "subscriber_last_name": performer.last_name,
            "subscriber_first_name": performer.first_name,
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

    if len(curr_group_ids) == 0:
        # omit subscribers who have zero performances for this playlist
        relevant_data = {
            key: value for (key, value) in data.items() if len(value.keys()) > 5
        }
        # ^ The test, > 5, must correspond to the number of fields written to data for each performance
    else:
        relevant_data = data

    # add creator's own performances
    for performer in [request.user]:
        relevant_data[performer] = {
            "subscriber": performer,  # n.b. not a string!
            "subscriber_name": performer.get_full_name(),
            "subscriber_last_name": "*" + str(performer.last_name).upper() + "*",
            "subscriber_first_name": "*" + str(performer.first_name).upper() + "*",
            "groups": ", ".join([]),
            **performance_dict.get(str(performer), {}),
        }

    # get playlist keys
    relevant_data_keys_per_performer = [
        value.keys() for (key, value) in relevant_data.items()
    ]
    compiled_playlist_keys = []
    for i in range(0, len(relevant_data_keys_per_performer)):
        playlist_keys = [
            key
            for key in relevant_data_keys_per_performer[i]
            if re.match("^[0-9]+$", key) or re.match("^P[A-Z][0-9]+[A-Z]+$", key)
        ]
        for j in range(0, len(playlist_keys)):
            if playlist_keys[j] not in compiled_playlist_keys:
                compiled_playlist_keys.append(playlist_keys[j])

    # Sort playlist keys: playlist IDs first, according to their order of presentation in the course, then legacy order values
    pco = PlaylistCourseOrdered.objects.filter(course_id=course._id)
    url_id_to_order = {}
    for i in range(0, len(pco)):
        url_id_to_order[pco[i].playlist.id] = pco[i].order
    compiled_playlist_keys.sort(
        key=lambda p: (
            int(p) if re.match("^[0-9]+$", p) else -1,  # order
            0 if url_id_to_order.get(str(p)) else 1,
            str(p)
            if re.match("^P[A-Z][0-9]+[A-Z]+$", p)
            and not url_id_to_order.get(
                str(p)
            )  # playlist.id of playlists not longer in course
            else "O",  # show as de-accessioned in the table
            url_id_to_order[str(p)]
            if re.match("^P[A-Z][0-9]+[A-Z]+$", p)
            and url_id_to_order.get(str(p))  # playlist.id of playlists in course
            else None,
        ),
        reverse=False,
    )

    table = CourseActivityTable(
        data=relevant_data.values(),
        extra_columns=[
            (
                str(idx),
                PlaylistActivityColumn(
                    verbose_name=playlist_column_verbose_name(str(idx), course),
                    empty_values=(()),
                    orderable=False,
                ),
            )
            for idx in compiled_playlist_keys
        ],
    )

    if len(curr_group_ids) == 0:
        table.exclude = ("groups",)

    RequestConfig(request, paginate={"per_page": subscribers_per_page}).configure(table)

    return render(
        request,
        "dashboard/course-activity.html",
        {
            "table": table,
            "course_id": course_id,
            "title": course.title,
            "filters": filters,
        },
    )
