from django.urls import path

from apps.accounts.views import LogoutView, register, login, forgot_password_view

urlpatterns = [
    path('register/', register, name='registration'),
    path('login/', login, name='custom-login'),
    path('logout/', LogoutView.as_view(), name='custom-logout'),
    path('forgot-password/', forgot_password_view, name='forgot-password')
]
