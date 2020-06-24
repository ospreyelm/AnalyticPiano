
from django.urls import path
from . import views


app_name = 'jasmine'

urlpatterns = [
    path('', views.run_tests, name='run_tests'),
]