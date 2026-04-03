from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
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
        "join_code": group.join_code,
        "join_url": request.build_absolute_uri(reverse("dashboard:join-group")),
    }

    if request.method == "POST":
        form = DashboardGroupEditForm(
            data=request.POST, instance=group, user=request.user
        )
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
            elif "duplicate" in request.POST:
                members = group.members.all()
                group.id = None
                group.join_code = None  # force new unique code on duplicate
                group = group.save()
                group.members.set(members)
                group.save()
                success_url = reverse(
                    "dashboard:edit-group", kwargs={"group_id": group.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been duplicated successfully.",
                )
            else:
                success_url = reverse("dashboard:groups-list")
            return redirect(success_url)

        context["form"] = form
        return render(request, "dashboard/add-group.html", context)
    else:
        form = DashboardGroupEditForm(instance=group, user=request.user)

    context["form"] = form

    # Build members table for display
    members_qs = group.members.all()
    members_table = GroupMembersTable(
        [{"name": str(m), "id": m.id, "group_id": group.id} for m in members_qs]
    )
    RequestConfig(request).configure(members_table)
    context["members_table"] = members_table

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

    member = get_object_or_404(User, id=member_id)
    group.members.remove(member)
    return redirect(reverse("dashboard:edit-group", kwargs={"group_id": group.id}))


@login_required
def regenerate_join_code_view(request, group_id):
    """Teacher-only POST: regenerate the join code for their group."""
    group = get_object_or_404(Group, id=group_id)

    if request.user != group.manager:
        raise PermissionDenied

    if request.method == "POST":
        group.join_code = None  # triggers auto-generation in save()
        group.save()
        messages.success(request, "Join code regenerated successfully.")

    return redirect(reverse("dashboard:edit-group", kwargs={"group_id": group.id}))


@login_required
def join_group_view(request):
    """Student view: enter a join code to self-enrol in a group."""
    if request.method == "POST":
        code = request.POST.get("join_code", "").strip().upper()
        if not code:
            messages.error(request, "Please enter a join code.")
            return render(request, "dashboard/join-group.html", {"join_code": ""})

        try:
            group = Group.objects.get(join_code=code)
        except Group.DoesNotExist:
            messages.error(
                request, f"No group found with code \"{code}\". Please check the code and try again."
            )
            return render(request, "dashboard/join-group.html", {"join_code": code})

        if request.user == group.manager:
            messages.info(request, f"You are the teacher of \"{group.name}\" — you cannot join your own group as a student.")
            return render(request, "dashboard/join-group.html", {"join_code": code})

        if group.members.filter(pk=request.user.pk).exists():
            messages.info(request, f"You are already a member of \"{group.name}\".")
        else:
            group.members.add(request.user)
            messages.success(request, f"You have joined the group \"{group.name}\".")

        return redirect(reverse("dashboard:index"))

    # GET
    prefill = request.GET.get("code", "").upper()
    return render(request, "dashboard/join-group.html", {"join_code": prefill})
