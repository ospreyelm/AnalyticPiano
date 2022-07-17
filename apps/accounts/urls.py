from django.urls import path

from apps.accounts.views import (
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    register,
    login,
)

urlpatterns = [
    path("register/", register, name="registration"),
    path("login/", login, name="custom-login"),
    path("logout/", LogoutView.as_view(), name="custom-logout"),
    # path("forgot-password/", forgot_password_view, name="forgot-password"),
    path("reset-password/", PasswordResetView.as_view(), name="reset-password"),
    path("reset-password-done/", PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "reset-password-confirm/<str:uidb64>/<str:token>",
        PasswordResetConfirmView.as_view(),
        # different naming pattern because the email is generated with a URL to this name
        name="password_reset_confirm",
    ),
]
