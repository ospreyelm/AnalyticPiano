from django.urls import include, path
from django.views.generic.base import RedirectView

from django.contrib import admin # enable admin
admin.autodiscover()

import lab.urls

admin.site.site_header = "Analytic Piano • Admin Main Menu"
admin.site.site_title = "Analytic Piano"
admin.site.index_title = "Admin Main Menu"

urlpatterns = [
    path("", include(lab.urls)),
    path("accounts/", include("apps.accounts.urls"), name="accounts"),
    path("dashboard/", include("apps.dashboard.urls")),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),# enable admin documentation
    path("analytic-piano-app-admin/", admin.site.urls, name="admin"),# enable admin
]

handler404 = "harmony.views.error_404"
