from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django_tables2 import RequestConfig

from apps.dashboard.forms import DashboardAddPlaylistForm
from apps.dashboard.tables import PlaylistsListTable
from apps.exercises.models import Playlist


@login_required
def playlists_list_view(request):
    playlists = Playlist.objects.filter(
        authored_by=request.user
    ).select_related('authored_by')

    table = PlaylistsListTable(playlists)

    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    return render(request, "dashboard/playlists-list.html", {
        "table": table,
    })


@login_required
def playlist_add_view(request):
    if request.method == 'POST':
        form = DashboardAddPlaylistForm(data=request.POST)
        form.context = {'user': request.user}
        if form.is_valid():
            playlist = form.save(commit=False)
            playlist.authored_by = request.user
            playlist.save()
            return redirect('dashboard:playlists-list')
    else:
        form = DashboardAddPlaylistForm()

    return render(request, "dashboard/playlist.html", {
        "form": form
    })


@login_required
def playlist_edit_view(request, playlist_name):
    playlist = get_object_or_404(Playlist, name=playlist_name)

    if request.method == 'POST':
        form = DashboardAddPlaylistForm(data=request.POST, instance=playlist)
        form.context = {'user': request.user}
        if form.is_valid():
            playlist = form.save(commit=False)
            playlist.authored_by = request.user
            playlist.save()
            return redirect('dashboard:playlists-list')
    else:
        form = DashboardAddPlaylistForm(instance=playlist)

    return render(request, "dashboard/playlist.html", {
        "form": form
    })


@login_required
def playlist_delete_view(request, playlist_name):
    playlist = get_object_or_404(Playlist, name=playlist_name)
    if playlist.authored_by != request.user:
        raise PermissionDenied

    if playlist.has_been_performed:
        raise ValidationError('Playlists that have been performed cannot be deleted.')

    playlist.delete()
    return redirect('dashboard:playlists-list')
