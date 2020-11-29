from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from apps.exercises.models import Exercise, Playlist, PerformanceData, Course
from apps.exercises.forms import ExerciseForm, PlaylistForm, PerformanceDataForm, CourseForm


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    form = ExerciseForm
    list_display = ('id', 'authored_by', 'is_public', 'created', 'updated', 'show_on_site')
    list_filter = ('authored_by__email', 'is_public')
    search_fields = ('id',)
    readonly_fields = ('id', 'authored_by', 'created', 'updated', 'show_on_site')
    raw_id_fields = ('authored_by',)
    fieldsets = (
        ('General Info', {
            'fields': (
                ('id', 'authored_by', 'type', 'staff_distribution', 'show_on_site'),
                ('created', 'updated'),
                'is_public'),
        }),
        ('Exercise Data', {
            'fields': ('rhythm_value', ('intro_text', 'review_text'), 'data')
        })
    )
    save_on_top = True

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(ExerciseAdmin, self).get_form(request, obj, change, **kwargs)
        form.context = {'user': request.user}
        return form

    def show_on_site(self, obj):
        if not obj.pk:
            return ''
        link = reverse('lab:exercise-view', kwargs={'exercise_id': obj.id})
        link = "<a href='%s' target='_blank' style='font-size: medium'>Show On Site</a><br>" % link
        return mark_safe(link)

    show_on_site.short_description = ''


@admin.register(Playlist)
class PlaylistAdmin(DynamicArrayMixin, admin.ModelAdmin):
    form = PlaylistForm
    list_display = ('name', 'exercise_links', 'authored_by',
                    'created', 'updated', 'show_on_site')
    list_filter = ('authored_by__email',)
    search_fields = ('name', 'exercises',)
    readonly_fields = ('id', 'authored_by', 'created', 'updated', 'exercise_links',
                       'performances', 'transposition_matrix', 'transposed_exercises_display',
                       'show_on_site')
    raw_id_fields = ('authored_by',)
    fieldsets = (
        ('General Info', {
            'fields': (('name', 'show_on_site'),
                       'id',
                       'authored_by',
                       ('created', 'updated')),
        }),
        ('Exercises', {
            'fields': ('performances',
                       'exercises',
                       'exercise_links')
        }),
        ('Transpose', {
            'fields': ('transpose_requests',
                       'transposition_type',
                       # 'transposition_matrix',
                       'transposed_exercises_display')
        })
    )
    save_on_top = True

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

    def show_on_site(self, obj):
        if not obj.pk:
            return ''
        link = reverse('lab:exercise-groups', kwargs={'group_name': obj.name})
        link = "<a href='%s' target='_blank' style='font-size: medium'>Show On Site</a><br>" % link
        return mark_safe(link)

    show_on_site.short_description = ''

    def performances(self, obj):
        if not (obj and obj._id):
            return '-'
        link = reverse('lab:performance-report', kwargs={'playlist_id': obj.id})
        return mark_safe("<a href='%s'>Show Data</a><br>" % link)

    performances.allow_tags = True
    performances.short_description = 'Performances'

    def transposed_exercises_display(self, obj):
        return ','.join(str(id_) for id_ in obj.transposed_exercises_ids) if obj.is_transposed() else ''

    transposed_exercises_display.short_description = 'Exercises Transposed'


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


@admin.register(Course)
class CourseAdmin(DynamicArrayMixin, admin.ModelAdmin):
    form = CourseForm
    list_display = ('title', 'playlist_links', 'authored_by',
                    'created', 'updated', 'show_on_site')
    list_filter = ('authored_by__email',)
    search_fields = ('title', 'exercises',)
    readonly_fields = ('id', 'authored_by', 'created', 'updated', 'playlist_links',
                       'show_on_site')
    raw_id_fields = ('authored_by',)
    fieldsets = (
        ('General Info', {
            'fields': (('title', 'show_on_site'),
                       'slug',
                       'id',
                       'authored_by',
                       ('created', 'updated')),
        }),
        ('Playlists', {
            'fields': ('playlists',
                       'playlist_links')
        })
    )
    save_on_top = True

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(CourseAdmin, self).get_form(request, obj, change, **kwargs)
        form.context = {'user': request.user}
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.authored_by = request.user
        obj.save()

    def playlist_links(self, obj):
        links = ''
        playlists = Playlist.objects.filter(name__in=obj.playlists.split(','))
        for playlist in playlists:
            link = reverse('admin:%s_%s_change' % ('exercises', 'playlist'), args=(playlist._id,))
            links += "<a href='%s'>%s</a><br>" % (link, playlist.name)
        return mark_safe(links)

    playlist_links.allow_tags = True
    playlist_links.short_description = 'Playlist Links'

    def show_on_site(self, obj):
        if not obj.pk:
            return ''
        link = reverse('lab:course-view', kwargs={'course_slug': obj.slug})
        link = "<a href='%s' target='_blank' style='font-size: medium'>Show On Site</a><br>" % link
        return mark_safe(link)

    show_on_site.short_description = ''
