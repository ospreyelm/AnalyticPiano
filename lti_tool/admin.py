from django.contrib import admin
import nested_admin

from .forms import ExerciseForm
from .models import Exercise, LTICourse, Unit


class ExerciseAdminInline(nested_admin.NestedTabularInline):
    model = Exercise
    extra = 1


class UnitAdminInline(nested_admin.NestedTabularInline):
    model = Unit
    inlines = [ExerciseAdminInline]
    extra = 1


@admin.register(LTICourse)
class CourseAdmin(nested_admin.NestedModelAdmin):
    inlines = [UnitAdminInline]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    inlines = [ExerciseAdminInline]
    readonly_fields = ('created', 'updated')


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    form = ExerciseForm
