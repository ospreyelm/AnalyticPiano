from django.contrib import admin as django_admin
from django.contrib.admin import ModelAdmin
from django.contrib.auth import admin, get_user_model
from django.contrib.auth.admin import UserChangeForm, UserCreationForm
from django.contrib.auth.forms import AdminPasswordChangeForm

from apps.accounts.forms import UserAdminCreationForm
from apps.accounts.models import Group

User = get_user_model()


class UserAdmin(admin.UserAdmin):
    fieldsets = (
        (
            "Account Information",
            {
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password",
                    "preferences",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                    "_supervisors",
                ),
            },
        ),
    )
    form = UserChangeForm
    add_form = UserAdminCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "is_superuser",
    )

    search_fields = ("email",)
    ordering = (
        "-is_active",
        "-is_superuser",
        "-is_staff",
        "last_name",
        "first_name",
        "id",
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


class GroupAdmin(ModelAdmin):
    pass


django_admin.site.register(User, UserAdmin)
django_admin.site.register(Group, GroupAdmin)
