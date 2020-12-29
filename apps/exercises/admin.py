from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from apps.exercises.forms import ExerciseForm, PlaylistForm, PerformanceDataForm, CourseForm
from apps.exercises.models import Exercise, Playlist, PerformanceData, Course


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    form = ExerciseForm
    list_display = ('id', 'show_on_site', 'authored_by', 'is_public', 'created', 'updated')
    list_filter = ('authored_by__email', 'is_public')
    search_fields = ('id',)
    readonly_fields = ('id', 'authored_by', 'created', 'updated', 'show_on_site')
    raw_id_fields = ('authored_by',)
    fieldsets = (
        ('Exercise Information', {
            'fields': (('id', 'show_on_site', 'authored_by', 'is_public'), 'name')
            # ('created', 'updated')
        }),
        ('Options', {
            'fields': (('type', 'staff_distribution', 'rhythm'),)

        }),
        ('Accompanying Text', {
            'fields': (
                ('intro_text', 'review_text'),
                # 'data'
            )
        })
    )
    save_on_top = True
    save_as = True

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(ExerciseAdmin, self).get_form(request, obj, change, **kwargs)
        form.context = {'user': request.user}
        return form

    def show_on_site(self, obj):
        if not obj.pk:
            return ''
        link = "<a href='%s' target='_blank'>Show On Site</a><br>" % obj.lab_url
        return mark_safe(link)

    show_on_site.short_description = 'Link'


@admin.register(Playlist)
class PlaylistAdmin(DynamicArrayMixin, admin.ModelAdmin):
    form = PlaylistForm
    list_display = ('name', 'show_on_site', 'authored_by',
                    'created', 'updated')
    list_filter = ('authored_by__email',)
    search_fields = ('name', 'exercises',)
    readonly_fields = ('id', 'authored_by', 'created', 'updated', 'exercise_links',
                       'performances', 'transposition_matrix', 'transposed_exercises_display',
                       'show_on_site')
    raw_id_fields = ('authored_by',)
    fieldsets = (
        ('Playlist Information', {
            'fields': (
                ('name', 'exercises', 'id', 'authored_by', 'show_on_site', 'performances'),
                # ('created', 'updated')
            ),
        }),
        ('Transpose', {
            'fields': (
                ('transposition_type', 'transpose_requests'),
                # 'transposition_matrix',
            ),
        }),
        ('Quick Edit Access for Associated Exercises', {
            'fields': (
                ('exercise_links'),
                ('transposed_exercises_display'),
            )
        })
    )
    save_on_top = True
    save_as = True

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
        for exercise in obj.exercise_objects:
            link = reverse('admin:%s_%s_change' % ('exercises', 'exercise'), args=(exercise._id,))
            links += "<a href='%s'>%s</a><br>" % (link, exercise.id)
        return mark_safe(links)

    exercise_links.allow_tags = True
    exercise_links.short_description = 'Exercise Links'

    def show_on_site(self, obj):
        if not obj.pk:
            return ''
        link = reverse('lab:exercise-groups', kwargs={'group_name': obj.name})
        link = "<a href='%s' target='_blank'>Show On Site</a><br>" % link
        return mark_safe(link)

    show_on_site.short_description = 'Link'

    def performances(self, obj):
        if not (obj and obj._id):
            return '-'
        link = reverse('lab:performance-report', kwargs={'playlist_id': obj.id})
        return mark_safe("<a href='%s'>Review Data</a><br>" % link)

    performances.allow_tags = True
    performances.short_description = 'Performance Data'

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
    list_display = ('title', 'show_on_site', 'authored_by',
                    'created', 'updated')
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
    save_as = True

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
        playlists = Playlist.objects.filter(id__in=obj.playlists.split(','))
        for playlist in playlists:
            link = reverse('admin:%s_%s_change' % ('exercises', 'playlist'), args=(playlist._id,))
            links += "<a href='%s'>%s</a><br>" % (link, playlist.id)
        return mark_safe(links)

    playlist_links.allow_tags = True
    playlist_links.short_description = 'Playlist Links'

    def show_on_site(self, obj):
        if not obj.pk:
            return ''
        link = reverse('lab:course-view', kwargs={'course_slug': obj.slug})
        link = "<a href='%s' target='_blank'>Show On Site</a><br>" % link
        return mark_safe(link)

    show_on_site.short_description = 'Link'
