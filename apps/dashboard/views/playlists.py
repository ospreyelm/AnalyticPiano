from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.urls import reverse
from django_tables2 import RequestConfig

from apps.dashboard.forms import DashboardPlaylistForm
from apps.dashboard.tables import PlaylistsListTable
from apps.dashboard.filters import ListIDFilter, PlaylistListNameFilter
from apps.exercises.models import ExercisePlaylistOrdered, Playlist

import re

@login_required
def playlists_list_view(request):
    playlists_author = request.user
    playlists = Playlist.objects.filter(authored_by=playlists_author).select_related(
        "authored_by"
    )

    playlist_name_filter = PlaylistListNameFilter(queryset=playlists, data=request.GET)
    playlist_name_filter.form.is_valid()
    name = playlist_name_filter.form.cleaned_data["name"]

    if name:
        playlists = playlists.filter(name__contains=name) # __icontains to ignore case

    playlist_id_filter = ListIDFilter(queryset=playlists, data=request.GET)
    playlist_id_filter.form.is_valid()
    min_id = playlist_id_filter.form.cleaned_data["min_id"]
    max_id = playlist_id_filter.form.cleaned_data["max_id"]

    pid_regex = re.compile(r'^P[A-Z][0-9]{2}[A-Z]{2}$')
    if min_id:
        min_id = 'PA00AA'[:max(0,6-len(min_id)):] + min_id.upper()[:6]
        if pid_regex.match(min_id):
            playlists = playlists.filter(id__gte=min_id.upper())
    if max_id and len(max_id) > 0: # should be redundant
        max_id = 'PA00AA'[:max(0,6-len(max_id)):] + max_id.upper()[:6]
        if pid_regex.match(max_id):
            playlists = playlists.filter(id__lte=max_id.upper())

    me = request.user

    table = PlaylistsListTable(playlists)

    RequestConfig(request, paginate={"per_page": 50}).configure(table)
    return render(
        request,
        "dashboard/playlists-list.html",
        {
            "table": table,
            "playlists_author": playlists_author,
            "me": me,
            "filters": {"name": playlist_name_filter, "id": playlist_id_filter},
        },
    )


@login_required
def playlist_add_view(request):
    context = {
        "verbose_name": Playlist._meta.verbose_name,
        "verbose_name_plural": Playlist._meta.verbose_name_plural,
    }

    if request.method == "POST":
        form = DashboardPlaylistForm(data=request.POST, user=request.user)
        form.context = {"user": request.user}
        if form.is_valid():
            playlist = form.save(commit=False)
            playlist.save()
            exercises = form.cleaned_data["exercises"]

            # create and save new EPOs
            for exercise, through_data in exercises:
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist, exercise=exercise, **through_data
                )

            if (
                "save-and-continue" in request.POST
                or "save-and-preview" in request.POST
            ):
                success_url = reverse(
                    "dashboard:edit-playlist", kwargs={"playlist_id": playlist.id}
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} has been saved successfully.",
                )
            else:
                success_url = reverse("dashboard:playlists-list")
            return redirect(success_url)
        context["form"] = form
        return render(request, "dashboard/content.html", context)

    else:
        form = DashboardPlaylistForm(
            initial=request.session.get("clone_data"), user=request.user
        )
        request.session["clone_data"] = None

    context["form"] = form
    return render(request, "dashboard/content.html", context)


@login_required
def playlist_edit_view(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id)

    if request.user != playlist.authored_by:
        raise PermissionDenied

    context = {
        "verbose_name": playlist._meta.verbose_name,
        "verbose_name_plural": playlist._meta.verbose_name_plural,
        "has_been_performed": playlist.has_been_performed,
        "redirect_url": reverse("dashboard:playlists-list"),
        "delete_url": reverse(
            "dashboard:delete-playlist", kwargs={"playlist_id": playlist_id}
        ),
        "preview_url": request.build_absolute_uri(
            reverse("lab:playlist-view", kwargs={"playlist_id": playlist.id})
        ),
        "editing": True,
    }

    PROTECT_PLAYLIST_CONTENT = playlist.has_been_performed

    if request.method == "POST":
        form = DashboardPlaylistForm(
            data=request.POST, instance=playlist, user=request.user
        )
        form.context = {"user": request.user}
        if form.is_valid():
            if PROTECT_PLAYLIST_CONTENT:
                playlist.id = playlist_id  ## critical in case user tries to edit playlist name and gets a bad redirect
                ## only alter is_public, name fields
                ## under no circumstances allow other changes to data
                playlist.save(update_fields=["name", "is_public"])
                ## ^ is this ok?
            else:
                playlist = form.save(commit=False)
                playlist.save()

                initial_epos = ExercisePlaylistOrdered.objects.filter(playlist=playlist)
                initial_exercises = [epo.exercise for epo in initial_epos]
                exercise_pairs = form.cleaned_data["exercises"]
                new_exercises = [exercise_pair[0] for exercise_pair in exercise_pairs]

                # edit or add new EPOs
                for exercise, through_data in exercise_pairs:
                    ExercisePlaylistOrdered.objects.update_or_create(
                        exercise=exercise, playlist=playlist, defaults=through_data
                    )

                # delete removed EPOs
                for exercise in initial_exercises:
                    if exercise not in new_exercises:
                        ExercisePlaylistOrdered.objects.filter(
                            exercise=exercise, playlist=playlist
                        ).delete()

            if (
                "save-and-continue" in request.POST
                or "save-and-preview" in request.POST
            ):
                success_url = reverse(
                    "dashboard:edit-playlist", kwargs={"playlist_id": playlist.id}
                )
                messages.add_message(
                    request, messages.SUCCESS, f"{context['verbose_name']} saved"
                )
            elif "save-and-edit-previous" in request.POST:
                success_url = reverse(
                    "dashboard:edit-playlist",
                    kwargs={
                        "playlist_id": playlist.get_previous_authored_playlist().id
                    },
                )
            elif "save-and-edit-next" in request.POST:
                success_url = reverse(
                    "dashboard:edit-playlist",
                    kwargs={"playlist_id": playlist.get_next_authored_playlist().id},
                )
            elif "duplicate" in request.POST:
                playlist._id = None
                playlist.id = None
                playlist = playlist.save()
                exercise_pairs = form.cleaned_data["exercises"]

                # edit or add new EPOs
                for exercise, through_data in exercise_pairs:
                    ExercisePlaylistOrdered.objects.update_or_create(
                        exercise=exercise,
                        playlist=playlist,
                        defaults=through_data,
                    )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"{context['verbose_name']} successfully duplicated",
                )
                return redirect("dashboard:edit-playlist", playlist.id)
            else:
                success_url = reverse("dashboard:playlists-list")
            return redirect(success_url)
        context["form"] = form
        return render(request, "dashboard/content.html", context)

    form = DashboardPlaylistForm(instance=playlist, user=request.user)

    # if playlist.has_been_performed:
    #     ## CAUSES BIG PROBLEMS! DESTROYS FORM VALIDATION
    #     form = DashboardPlaylistForm(instance=playlist, disable_fields=True)

    context["form"] = form
    return render(request, "dashboard/edit-playlist.html", context)


@login_required
def playlist_delete_view(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id)

    if request.user != playlist.authored_by:
        raise PermissionDenied

    if request.method == "POST":
        if playlist.has_been_performed:
            raise ValidationError(
                "Playlists that have been performed cannot be deleted."
            )
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
