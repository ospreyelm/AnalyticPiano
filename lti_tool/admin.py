import nested_admin

from apps.exercises.models import Exercise


class ExerciseAdminInline(nested_admin.NestedTabularInline):
    model = Exercise
    extra = 1


#
#
# class UnitAdminInline(nested_admin.NestedTabularInline):
#     model = Unit
#     inlines = [ExerciseAdminInline]
#     extra = 1
#
#
# @admin.register(LTICourse)
# class CourseAdmin(nested_admin.NestedModelAdmin):
#     inlines = [UnitAdminInline]
#
#
# @admin.register(Unit)
# class UnitAdmin(admin.ModelAdmin):
#     inlines = [ExerciseAdminInline]
#     readonly_fields = ('created', 'updated')
#

