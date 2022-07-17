from copy import copy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django_tables2 import RequestConfig


from apps.dashboard.forms import DashboardPlaylistForm
from apps.dashboard.tables import PlaylistsListTable
from apps.exercises.models import Playlist


@login_required
def playlists_list_view(request):
    playlists = Playlist.objects.filter(authored_by=request.user).select_related("authored_by")

    table = PlaylistsListTable(playlists)
    playlists_author = request.user

    RequestConfig(request, paginate={"per_page": 50}).configure(table)
    return render(request, "dashboard/playlists-list.html", {"table": table, "playlists_author": playlists_author})


@login_required
def playlist_add_view(request):
    context = {
        "verbose_name": Playlist._meta.verbose_name,
        "verbose_name_plural": Playlist._meta.verbose_name_plural,
    }

    if request.method == "POST":
        form = DashboardPlaylistForm(data=request.POST)
        form.context = {"user": request.user}
        if form.is_valid():
            playlist = form.save(commit=False)
            playlist.authored_by = request.user
            playlist.save()
            if "save-and-continue" in request.POST:
                success_url = reverse("dashboard:edit-playlist", kwargs={"playlist_slug": playlist.slug})
                messages.add_message(
                    request, messages.SUCCESS, f"{context['verbose_name']} has been saved successfully."
                )
            else:
                success_url = reverse("dashboard:playlists-list")
            return redirect(success_url)
        context["form"] = form
        return render(request, "dashboard/content.html", context)

    else:
        form = DashboardPlaylistForm(initial=request.session.get("clone_data"))
        request.session["clone_data"] = None

    context["form"] = form
    return render(request, "dashboard/content.html", context)


@login_required
def playlist_edit_view(request, playlist_slug):
    playlist = get_object_or_404(Playlist, slug=playlist_slug)

    if request.user != playlist.authored_by:
        raise PermissionDenied

    context = {
        "verbose_name": playlist._meta.verbose_name,
        "verbose_name_plural": playlist._meta.verbose_name_plural,
        "has_been_performed": playlist.has_been_performed,
        "redirect_url": reverse("dashboard:playlists-list"),
        "delete_url": reverse("dashboard:delete-playlist", kwargs={"playlist_slug": playlist_slug}),
    }

    PROTECT_PLAYLIST_CONTENT = playlist.has_been_performed

    if request.method == "POST":
        form = DashboardPlaylistForm(data=request.POST, instance=playlist)
        form.context = {"user": request.user}
        if form.is_valid():
            if "duplicate" in request.POST:
                unique_fields = Playlist.get_unique_fields()
                clone_data = copy(form.cleaned_data)
                for field in clone_data:
                    if field in unique_fields:
                        clone_data[field] = None
                request.session["clone_data"] = clone_data
                return redirect("dashboard:add-playlist")

            if PROTECT_PLAYLIST_CONTENT:
                playlist.slug = (
                    playlist_slug  ## critical in case user tries to edit playlist name and gets a bad redirect
                )
                ## only alter is_public field
                ## under no circumstances allow other changes to data
                playlist.save(update_fields=["is_public"])
                ## ^ is this ok?
            else:
                playlist = form.save(commit=False)
                playlist.authored_by = request.user
                ## ^ original authorship of playlist should not change
                playlist.save()

            if "save-and-continue" in request.POST:
                success_url = reverse("dashboard:edit-playlist", kwargs={"playlist_slug": playlist.slug})
                messages.add_message(request, messages.SUCCESS, f"{context['verbose_name']} saved")
            else:
                success_url = reverse("dashboard:playlists-list")
            return redirect(success_url)
        context["form"] = form
        return render(request, "dashboard/content.html", context)

    form = DashboardPlaylistForm(instance=playlist)

    # if playlist.has_been_performed:
    #     ## CAUSES BIG PROBLEMS! DESTROYS FORM VALIDATION
    #     form = DashboardPlaylistForm(instance=playlist, disable_fields=True)

    context["form"] = form
    return render(request, "dashboard/content.html", context)


@login_required
def playlist_delete_view(request, playlist_slug):
    playlist = get_object_or_404(Playlist, slug=playlist_slug)

    if request.user != playlist.authored_by:
        raise PermissionDenied

    if request.method == "POST":
        if playlist.has_been_performed:
            raise ValidationError("Playlists that have been performed cannot be deleted.")
        playlist.delete()
        return redirect("dashboard:playlists-list")

    context = {
        "obj": playlist,
        "obj_name": playlist.name,
        "verbose_name": playlist._meta.verbose_name,
        "verbose_name_plural": playlist._meta.verbose_name_plural,
        "has_been_performed": playlist.has_been_performed,
        "redirect_url": reverse("dashboard:playlists-list"),
    }
    return render(request, "dashboard/delete-confirmation.html", context)
