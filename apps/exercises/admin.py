from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.exercises.models import Exercise, Playlist, PerformanceData
from apps.exercises.forms import ExerciseForm, PlaylistForm, PerformanceDataForm


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    form = ExerciseForm
    list_display = ('id', 'authored_by', 'is_public', 'created', 'updated')
    list_filter = ('authored_by__email', 'is_public')
    search_fields = ('id',)
    readonly_fields = ('id', 'authored_by', 'created', 'updated')
    raw_id_fields = ('authored_by',)
    fieldsets = (
        ('General Info', {
            'fields': ('id', 'authored_by', 'is_public'),
        }),
        ('Exercise Data', {
            'fields': ('data', 'type', 'intro_text', 'review_text', 'rhythm_value')
        }),
        ('Date Info', {
            'fields': ('created', 'updated')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.authored_by = request.user
        obj.save()


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    form = PlaylistForm
    list_display = ('name', 'exercise_links', 'authored_by', 'created', 'updated')
    list_filter = ('authored_by__email',)
    search_fields = ('name', 'exercises',)
    readonly_fields = ('id', 'authored_by', 'created', 'updated', 'exercise_links', 'performances')
    raw_id_fields = ('authored_by',)
    fieldsets = (
        ('General Info', {
            'fields': ('name', 'id', 'authored_by'),
        }),
        ('Exercises', {
            'fields': ('exercises', 'exercise_links', 'performances')
        }),
        ('Date Info', {
            'fields': ('created', 'updated')
        }),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(PlaylistAdmin, self).get_form(request, obj, change, **kwargs)
        form.context = {'user': request.user}
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.authored_by = request.user
        obj.save()

    def exercise_links(self, obj):
        links = ''
        exercises = Exercise.objects.filter(id__in=obj.exercises.split(','))
        for exercise in exercises:
            link = reverse('admin:%s_%s_change' % ('exercises', 'exercise'), args=(exercise._id,))
            links += "<a href='%s'>%s</a><br>" % (link, exercise.id)
        return mark_safe(links)

    exercise_links.allow_tags = True
    exercise_links.short_description = 'Exercise Links'

    def performances(self, obj):
        if not (obj and obj._id):
            return '-'
        link = reverse('lab:performance-report', kwargs={'playlist_id': obj.id})
        return mark_safe("<a href='%s'>Show Data</a><br>" % link)

    performances.allow_tags = True
    performances.short_description = 'Performances'


@admin.register(PerformanceData)
class PerformanceDataAdmin(admin.ModelAdmin):
    form = PerformanceDataForm
    list_display = ('user', 'playlist', 'created', 'updated')
    list_filter = ('user__email', 'playlist__name')
    search_fields = ('user__email', 'playlist__name',)
    readonly_fields = ('created', 'updated')
    raw_id_fields = ('user', 'supervisor', 'playlist')
    fieldsets = (
        ('General Info', {
            'fields': ('user', 'supervisor', 'playlist'),
        }),
        ('Performance Data', {
            'fields': ('data', 'playlist_performances')
        }),
        ('Date Info', {
            'fields': ('created', 'updated')
        }),
    )
