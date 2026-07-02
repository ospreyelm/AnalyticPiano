from django.contrib import admin

from apps.lti.models import LtiLineItem, LtiPlatform, LtiUserLink


@admin.register(LtiPlatform)
class LtiPlatformAdmin(admin.ModelAdmin):
    """The only place agreement_signed_at and is_active get set — not
    exposed to teachers, superuser-only by default admin permissions."""

    list_display = ("name", "issuer", "is_active", "agreement_signed_at", "is_ready_for_real_courses")
    list_filter = ("is_active",)
    search_fields = ("name", "issuer", "client_id")
    readonly_fields = ("is_ready_for_real_courses",)


@admin.register(LtiUserLink)
class LtiUserLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "sub")
    list_filter = ("platform",)
    search_fields = ("user__email", "sub")


@admin.register(LtiLineItem)
class LtiLineItemAdmin(admin.ModelAdmin):
    list_display = ("pco", "platform", "line_item_id")
    list_filter = ("platform",)
