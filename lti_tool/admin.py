from django.contrib import admin
from .models import LTICourse, LTIConsumer

class LTICourseAdmin(admin.ModelAdmin):
    pass

class LTIConsumerAdmin(admin.ModelAdmin):
    pass

admin.site.register(LTICourse, LTICourseAdmin)
admin.site.register(LTIConsumer, LTIConsumerAdmin)