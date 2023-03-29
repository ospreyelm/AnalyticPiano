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
        Group.objects.filter(manager=groups_author)
        .select_related("manager")
        .annotate(members_count=Count("members"))
    )
    me = request.user

    table = GroupsListTable(groups)

    RequestConfig(request, paginate={"per_page": 50}).configure(table)
    return render(
        request,
        "dashboard/groups-list.html",
        {"table": table, "groups_author": groups_author, "me": me},
    )


@login_required
def group_add_view(request):
    context = {
        "verbose_name": Group._meta.verbose_name,
        "verbose_name_plural": Group._meta.verbose_name_plural,
    }

    if request.method == "POST":
        form = DashboardGroupAddForm(request.POST, user=request.user)
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
        form = DashboardGroupAddForm(user=request.user)

    context["form"] = form
    return render(request, "dashboard/add-group.html", context)


def parse_member(user):
    return {"name": str(user), "id": user.id}


@login_required
def group_edit_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.user != group.manager:
        raise PermissionDenied

    context = {
        "verbose_name": Group._meta.verbose_name,
        "verbose_name_plural": Group._meta.verbose_name_plural,
        "editing": True,
    }

    if request.method == "POST":
        form = DashboardGroupEditForm(
            data=request.POST, instance=group, user=request.user
        )
        form.context = {"user": request.user}
        if form.is_valid():
            group = form.save(commit=False)
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
        form = DashboardGroupEditForm(instance=group, user=request.user)

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
