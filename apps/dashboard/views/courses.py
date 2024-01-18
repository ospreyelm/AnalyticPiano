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
from django_tables2 import RequestConfig, Column

from apps.dashboard.filters import (
    CourseActivityGroupsFilter,
    CourseActivityOrderFilter,
)
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
from apps.accounts.models import Group, User


@login_required
def courses_list_view(request, courses_author_id=None):
    if courses_author_id == None:
        courses_author = request.user
    else:
        courses_author = get_object_or_404(User, id=courses_author_id)
    courses = Course.objects.filter(authored_by=courses_author).select_related(
        "authored_by"
    )
    me = request.user

    table = CoursesListTable(courses)

    RequestConfig(request, paginate={"per_page": 50}).configure(table)
    return render(
        request,
        "dashboard/courses-list.html",
        {"table": table, "courses_author": courses_author, "me": me},
    )


@login_required
def courses_by_user_view(request, courses_author_id=None):
    return courses_list_view(request, courses_author_id)


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
            course.save()
            course.visible_to.set(form.cleaned_data["visible_to"])
            # TODO: a bit wasteful to save twice. however, committing the form gives errors for playlist field,
            #   so the mix of through-table M2M and normal M2M necessitates this. Revisit later.
            course.save()

            playlists = form.cleaned_data["playlists"]

            # create and save new EPOs
            for playlist, through_data in playlists:
                PlaylistCourseOrdered.objects.create(
                    course=course, playlist=playlist, **through_data
                )

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
    course = get_object_or_404(Course, id=course_id)

    if request.user != course.authored_by:
        raise PermissionDenied

    context = {
        "verbose_name": course._meta.verbose_name,
        "verbose_name_plural": course._meta.verbose_name_plural,
        "has_been_performed": False,  # may not be False but this removes irrelevant styling
        "redirect_url": reverse("dashboard:courses-list"),
        "editing": True,
        "user": request.user,
    }

    if request.method == "POST":
        form = DashboardCourseForm(
            data=request.POST, instance=course, user=request.user
        )
        form.context = {"user": request.user}
        if form.is_valid():
            course = form.save(commit=False)
            course.save()
            course.visible_to.set(form.cleaned_data["visible_to"])
            course.save()

            initial_pcos = PlaylistCourseOrdered.objects.filter(course=course)
            initial_playlists = [pco.playlist for pco in initial_pcos]
            playlist_pairs = form.cleaned_data["playlists"]
            new_playlists = [exercise_pair[0] for exercise_pair in playlist_pairs]

            # edit or add new PCOs
            for playlist, through_data in playlist_pairs:
                PlaylistCourseOrdered.objects.update_or_create(
                    playlist=playlist, course=course, defaults=through_data
                )

            # delete removed PCOs
            for playlist in initial_playlists:
                if playlist not in new_playlists:
                    PlaylistCourseOrdered.objects.filter(
                        playlist=playlist, course=course
                    ).delete()

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
                visible_to = course.visible_to.all()
                course._id = None
                course.id = None
                course.performance_dict = {}
                course = course.save()
                course.visible_to.set(visible_to)
                course.save()

                # edit or add new PCOs
                for playlist, through_data in playlist_pairs:
                    # adds PCOs linking playlists to new course, but without publish_date or due_date
                    PlaylistCourseOrdered.objects.update_or_create(
                        playlist=playlist,
                        course=course,
                        defaults={
                            k: v
                            for k, v in through_data.items()
                            # if k not in ["publish_date", "due_date"]
                        },
                    )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} successfully duplicated",
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


# Keys within a course's performance_dict that don't correspond with a playlist
reserved_dict_keys = {
    "performer",
    "performer_name",
    "performer_last_name",
    "performer_first_name",
    "groups",
    "time_elapsed",
}


@login_required
# @cache_page(60 * 15)
def course_activity_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user != course.authored_by:
        raise PermissionDenied

    # Change this to alter the number of displayed performers per page.
    performers_per_page = 35

    group_filter = CourseActivityGroupsFilter(
        queryset=course.visible_to.all(), data=request.GET
    )
    group_filter.form.is_valid()

    unitnumber_filter = CourseActivityOrderFilter(
        queryset=course.visible_to.all(), data=request.GET
    )
    unitnumber_filter.form.is_valid()

    curr_group_ids = [int(g) for g in group_filter.form.cleaned_data["groups"] or []]
    curr_groups = Group.objects.filter(id__in=curr_group_ids)

    performers = User.objects.filter(pk__in=request.user.content_permits)
    if len(curr_group_ids) > 0:
        performers = performers.filter(participant_groups__id__in=curr_group_ids)

    performance_dict = course.performance_dict
    data = {
        performer: {
            "performer": performer,  # n.b. not a string!
            "performer_name": performer.get_full_name(),
            "performer_last_name": performer.last_name,
            "performer_first_name": performer.first_name,
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
        # course's performers + author
        for performer in list(performers) + [request.user]
    }

    if len(curr_group_ids) == 0:
        # omit performers who have zero performances for this playlist
        relevant_data = {
            key: value for (key, value) in data.items() if len(value.keys()) > 5
        }
        # ^ The test, > 5, must correspond to the number of fields written to data for each performance
    else:
        relevant_data = data

    # get playlist keys
    relevant_data_keys_per_performer = [
        value.keys() for (key, value) in relevant_data.items()
    ]

    course_pcos = PlaylistCourseOrdered.objects.filter(
        course_id=course._id
    ).prefetch_related("playlist")

    min_unit_num = unitnumber_filter.form.cleaned_data["min_unit_num"]
    max_unit_num = unitnumber_filter.form.cleaned_data["max_unit_num"]
    filtered_unit_num = False
    if min_unit_num or max_unit_num:
        filtered_unit_num = True
        if min_unit_num:
            course_pcos = course_pcos.filter(order__gte=min_unit_num)
        if max_unit_num:
            course_pcos = course_pcos.filter(order__lte=max_unit_num)
    filtered_pco_ids = set([pco.playlist.id for pco in course_pcos])

    compiled_playlist_keys = set()
    for i in range(0, len(relevant_data_keys_per_performer)):
        # Combining existing playlist keys with any new keys from this performer
        compiled_playlist_keys = compiled_playlist_keys.union(
            set(
                [
                    key
                    for key in relevant_data_keys_per_performer[i]
                    if
                    # if this key corresponds to a playlist (order or id)
                    not key in reserved_dict_keys
                    # if this key should be filtered out based on the unit filter
                    and (not filtered_unit_num or key in filtered_pco_ids)
                ]
            )
        )

    for performer, performance_data in relevant_data.items():
        relevant_data[performer] = {
            k: v
            for k, v in performance_data.items()
            if k in compiled_playlist_keys or k in reserved_dict_keys
        }

    compiled_playlist_keys = list(compiled_playlist_keys)

    # Sort playlist keys: playlist IDs first, according to their order of presentation in the course, then legacy order values
    url_id_to_order = {}
    for i in range(0, len(course_pcos)):
        url_id_to_order[course_pcos[i].playlist.id] = course_pcos[i].order
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
        course=course,
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

    RequestConfig(request, paginate={"per_page": performers_per_page}).configure(table)

    return render(
        request,
        "dashboard/course-activity.html",
        {
            "table": table,
            "course_id": course_id,
            "title": course.title,
            "filters": {"group": group_filter, "unitnumber": unitnumber_filter},
        },
    )
