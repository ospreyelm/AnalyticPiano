from django.urls import include, path
from django.views.generic.base import RedirectView
from register import views as v
from lab.views import course_list_view
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

import jasmine.urls
import lab.urls
import lti_tool.urls

urlpatterns = [
    path('', RedirectView.as_view(url='/lab'), name='index'),
    path('lab/', include(lab.urls)),
    path('lti/', include(lti_tool.urls)),
    path('jasmine/', include(jasmine.urls)),
    path('admin/', admin.site.urls),
    path("register/", v.register, name="register"), 
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    path('courses/', course_list_view, name="course-list")

]

#Add Django site authentication urls (for login, logout, password management)

urlpatterns += [
    path('accounts/', include('django.contrib.auth.urls')),
]

