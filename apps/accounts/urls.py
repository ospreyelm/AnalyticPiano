from django.urls import path

from apps.accounts.views import LogoutView, register, login

urlpatterns = [
    path('register/', register, name='registration'),
    path('login/', login, name='custom-login'),
    path('logout/', LogoutView.as_view(), name='custom-logout'),
]
