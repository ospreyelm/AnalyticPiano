from django.urls import include, path
from django.views.generic.base import RedirectView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

import jasmine.urls
import lab.urls
import lti_tool.urls

urlpatterns = [
    path('', RedirectView.as_view(url='/lab'), name='index'),
    path('lab/', include(lab.urls)),
    path('accounts/', include('apps.accounts.urls'), name='accounts'),
    path('dashboard/', include('apps.dashboard.urls')),
    path('lti/', include(lti_tool.urls)),
    path('jasmine/', include(jasmine.urls)),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    path('admin/', admin.site.urls),
]
