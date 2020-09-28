from django.contrib import admin as django_admin
from django.contrib.auth import admin, get_user_model
from django.contrib.auth.admin import UserChangeForm, UserCreationForm
from django.contrib.auth.forms import AdminPasswordChangeForm

from apps.accounts.forms import UserAdminCreationForm

User = get_user_model()


class UserAdmin(admin.UserAdmin):
    fieldsets = (
        ('Account Information', {
            'fields': (
                'email',
                'first_name',
                'last_name',
                'password',

                # FIXME RAAAAAWW PASSSWORDD!!
                'raw_password',
                
                'is_staff',
                'is_superuser',
                'is_active',
                '_supervisors'
            ),
        }),


    )
    form = UserChangeForm
    add_form = UserAdminCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = (
        'email', 'is_staff', 'is_superuser', 'is_active', 'first_name', 'last_name'
    )

    search_fields = ('email',)
    ordering = ('id',)

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )


django_admin.site.register(User, UserAdmin)
