from curses.ascii import US
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from apps.dashboard.views.m2m_view import handle_m2m
from django_tables2 import RequestConfig

from apps.accounts.models import Group, User
from apps.dashboard.forms import DashboardGroupEditForm, DashboardGroupAddForm
from apps.dashboard.tables import GroupsListTable, GroupMembersTable


@login_required
def groups_list_view(request):
    groups_author = request.user
    groups = (
        Group.objects.filter(manager=request.user)
        .select_related("manager")
        .annotate(members_count=Count("members"))
    )

    table = GroupsListTable(groups)

    RequestConfig(request, paginate={"per_page": 50}).configure(table)
    return render(
        request,
        "dashboard/groups-list.html",
        {"table": table, "groups_author": groups_author},
    )


@login_required
def group_add_view(request):
    context = {
        "verbose_name": Group._meta.verbose_name,
        "verbose_name_plural": Group._meta.verbose_name_plural,
    }

    if request.method == "POST":
        form = DashboardGroupAddForm(request.POST)
        form.context = {"user": request.user}
        if form.is_valid():
            group = form.save()
            if "save-and-continue" in request.POST:
                success_url = reverse(
                    "dashboard:edit-group", kwargs={"group_id": group.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been saved successfully.",
                )
            else:
                success_url = reverse("dashboard:groups-list")
            return redirect(success_url)

        context["form"] = form
        return render(request, "dashboard/add-group.html", context)
    else:
        form = DashboardGroupAddForm()

    context["form"] = form
    return render(request, "dashboard/add-group.html", context)


def parse_member(user):
    return {"name": user.email, "id": user.id}


@login_required
def group_edit_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.user != group.manager:
        raise PermissionDenied

    members_list = list(map(parse_member, group.members.all()))

    context = {
        "verbose_name": Group._meta.verbose_name,
        "verbose_name_plural": Group._meta.verbose_name_plural,
        "editing": True,
        "m2m_added": {"members": members_list},
        "m2m_options": {
            "members": filter(
                lambda u: u not in group.members.all(), User.objects.all()
            ),
        },
    }

    if request.method == "POST":
        form = DashboardGroupEditForm(data=request.POST, instance=group)
        form.context = {"user": request.user}
        if form.is_valid():
            group = form.save(commit=False)
            added_member_id = request.POST.get("members_add")

            if added_member_id != "":
                group.members.add(User.objects.filter(id=added_member_id).first())
            handle_m2m(
                request,
                "members",
                {"group_id": group.id},
                "user_id",
                list(
                    map(
                        lambda u: User.objects.filter(id=u["id"]).first(),
                        members_list,
                    )
                ),
                parent_instance=group,
                ChildModel=User,
            )
            group.save()
            if "save-and-continue" in request.POST:
                success_url = reverse(
                    "dashboard:edit-group", kwargs={"group_id": group.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been saved successfully.",
                )
            else:
                success_url = reverse("dashboard:groups-list")
            return redirect(success_url)

        context["form"] = form
        return render(request, "dashboard/add-group.html", context)
    else:
        form = DashboardGroupEditForm(instance=group)

    context["form"] = form
    return render(request, "dashboard/add-group.html", context)


@login_required
def group_delete_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.user != group.manager:
        raise PermissionDenied

    if request.method == "POST":
        group.delete()
        return redirect("dashboard:groups-list")

    context = {
        "obj": group,
        "obj_name": group.name,
        "verbose_name": group._meta.verbose_name,
        "verbose_name_plural": group._meta.verbose_name_plural,
        "redirect_url": reverse("dashboard:groups-list"),
    }
    return render(request, "dashboard/delete-confirmation.html", context)


@login_required
def remove_member(request, group_id, member_id):
    group = get_object_or_404(Group, id=group_id)

    if request.user != group.manager:
        raise PermissionDenied

    group.remove_member(member_id)
    return redirect(reverse("dashboard:edit-group", kwargs={"group_id": group.id}))
