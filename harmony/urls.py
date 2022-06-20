from django.urls import include, path
from django.views.generic.base import RedirectView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin

admin.autodiscover()

import jasmine.urls
import lab.urls
import lti_tool.urls

admin.site.site_header = "Analytic Piano • Admin Main Menu"
admin.site.site_title = "Analytic Piano"
admin.site.index_title = "Admin Main Menu"

urlpatterns = [
    path('', include(lab.urls)),
    path('accounts/', include('apps.accounts.urls'), name='accounts'),
    path('dashboard/', include('apps.dashboard.urls')),
    path('lti/', include(lti_tool.urls)),
    path('jasmine/', include(jasmine.urls)),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    path('analytic-piano-app-admin/', admin.site.urls, name='admin'),
]

handler404 = 'harmony.views.error_404'

# FIXME remove after Sentry test was successful
def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns += [
    path('sentry-debug/', trigger_error),
]
