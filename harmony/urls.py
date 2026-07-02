from django.urls import include, path
from django.views.generic.base import RedirectView

from django.contrib import admin # enable admin
admin.autodiscover()

import lab.urls
from apps.exercises.views_tools import content_generation_view
from apps.dashboard.views.library import library_view, clone_course_view
from harmony.views import home_redirect

admin.site.site_header = "Admin"
admin.site.site_title = "Admin"
admin.site.index_title = "Admin"

urlpatterns = [
    path("", home_redirect, name="root-redirect"),
    path("play/", RedirectView.as_view(url="/s/"), name="play-redirect"),
    path("tools/content-generation/", content_generation_view, name="content-generation"),

    path("accounts/", include("apps.accounts.urls"), name="accounts"),
    path("dashboard/", include("apps.dashboard.urls")),
    path("s/", include("apps.student.urls")),
    path("teacher/", include("apps.teacher.urls")),
    path("lti/", include("apps.lti.urls")),
    path("", include(lab.urls)),

    path("library/", library_view, name="library"),
    path("library/clone-course/<str:course_id>/", clone_course_view, name="clone-course"),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),# enable admin documentation
    path("admin/", admin.site.urls, name="admin"),
]

handler404 = "harmony.views.error_404"
