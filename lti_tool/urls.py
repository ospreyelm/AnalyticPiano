from django.urls import path

from .views import LTILaunchView
from .views import LTIToolConfigView
from .views import logout_view
from .views import logged_out_view


app_name = 'lti'

urlpatterns = [
    path('', LTILaunchView.as_view(), name='index'),
    path('launch', LTILaunchView.as_view(), name='launch'),
    path('config', LTIToolConfigView.as_view(), name='config'),
    path('logout', logout_view, name="logout"),
    path('logged-out', logged_out_view, name="logged-out"),
]