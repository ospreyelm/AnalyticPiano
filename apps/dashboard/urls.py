from django.urls import path

from apps.dashboard.views import (
    supervisors_view,
    unsubscribe_view,
    subscribers_view,
    remove_subscriber_view, performance_list_view, playlist_performance_view
)

app_name = 'dashboard'

urlpatterns = [
    # Supervisors / Subscribers
    path('supervisors/', supervisors_view, name="supervisors"),
    path('unsubscribe/<int:supervisor_id>/', unsubscribe_view, name="unsubscribe"),

    path('subscribers/', subscribers_view, name="subscribers"),
    path('remove-subscriber/<int:subscriber_id>/', remove_subscriber_view, name="remove-subscriber"),

    # Playlist Performance
    path('performances/<int:subscriber_id>/', performance_list_view,
         name="subscriber-performances"),
    path('performances/', performance_list_view, name="performed-playlists"),

    path('playlist-performance/<int:subscriber_id>/<str:playlist_id>/', playlist_performance_view,
         name="subscriber-playlist-performance"),
    path('playlist-performance/<str:playlist_id>/', playlist_performance_view, name="playlist-performance"),
]
