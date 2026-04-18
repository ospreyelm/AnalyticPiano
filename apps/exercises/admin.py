from django.contrib import admin
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
from django.contrib import messages
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from import_export.admin import ImportExportModelAdmin

from apps.exercises.forms import (
    ExerciseForm,
    PlaylistForm,
    PerformanceDataForm,
    CourseForm,
)
from apps.exercises.models import (
    Exercise, 
    Playlist, 
    PerformanceData, 
    Course,
    StudentSkillMastery,
    SkillPrerequisite,
    IdentificationAttempt
)

import re
import sys
import os

from apps.exercises.resources import ExerciseResource, PlaylistResource, CourseResource


@admin.register(Exercise)
class ExerciseAdmin(ImportExportModelAdmin):
    form = ExerciseForm
    list_display = (
        "id",
        "show_on_site",
        "authored_by",
        "is_public",
        "created",
        "updated",
    )
    list_filter = ("authored_by__email", "is_public")
    search_fields = ("id",)
    readonly_fields = ("id", "authored_by", "created", "updated", "show_on_site")
    raw_id_fields = ("authored_by",)
    fieldsets = (
        (
            "Exercise Information",
            {
                "fields": (
                    ("id", "show_on_site", "authored_by", "is_public"),
                    "description",
                    "locked",
                )
                # ('created', 'updated')
            },
        ),
        ("Options", {"fields": (("type", "staff_distribution", "rhythm"),)}),
        (
            "Accompanying Text",
            {
                "fields": (
                    ("intro_text"),
                    # 'data'
                )
            },
        ),
    )
    save_on_top = True
    save_as = True

    resource_class = ExerciseResource
    
    change_list_template = "admin/exercises/exercise/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-musicxml/',
                self.admin_site.admin_view(self.import_musicxml_view),
                name='exercises_exercise_import_musicxml',
            ),
        ]
        return custom_urls + urls

    def import_musicxml_view(self, request):
        if request.method == "POST":
            musicxml_file = request.FILES.get('musicxml_file')
            title = request.POST.get('title', '')
            is_public = request.POST.get('is_public') == 'on'
            start_measure = request.POST.get('start_measure', '')
            end_measure = request.POST.get('end_measure', '')
            
            if not musicxml_file:
                messages.error(request, "Please select a MusicXML file to upload.")
                return render(request, 'admin/exercises/exercise/import_musicxml.html')
            
            # Save uploaded file temporarily
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
                for chunk in musicxml_file.chunks():
                    tmp_file.write(chunk)
                tmp_path = tmp_file.name
            
            try:
                # Import the converter functions
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))
                from fetch_bach_chorales import m21_to_cir, build_events
                
                # Load MusicXML using music21
                from music21 import converter
                score = converter.parse(tmp_path)
                
                # Apply measure range if specified
                if start_measure and end_measure:
                    measures = score.measures(int(start_measure), int(end_measure))
                    score = measures
                elif start_measure:
                    measures = score.measures(int(start_measure), None)
                    score = measures
                
                # Convert to CIR
                cir = m21_to_cir(score)
                events = build_events(cir)
                
                # Convert Event objects to dictionaries for JSON serialization
                events_json = [
                    {
                        'start': event.start,
                        'perStaff': event.perStaff
                    }
                    for event in events
                ]
                
                # Create exercise with CIR format.
                # Use explicit instance.save() to avoid force_insert interactions with Exercise.save().
                exercise_data = {
                    'type': 'chorale',
                    'score': cir,
                    'events': events_json,
                }
                if title:
                    exercise_data['metadata'] = {'title': title}

                exercise = Exercise(
                    authored_by=request.user,
                    is_public=is_public,
                    data=exercise_data,
                )
                exercise.save()
                
                messages.success(
                    request, 
                    f'Successfully imported MusicXML as exercise {exercise.id}. '
                    f'<a href="{exercise.lab_url}" target="_blank">View on site</a>'
                )
                
                # Clean up temp file
                os.unlink(tmp_path)
                
                return redirect('admin:exercises_exercise_change', exercise.pk)
                
            except Exception as e:
                messages.error(request, f"Error importing MusicXML: {str(e)}")
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                return render(request, 'admin/exercises/exercise/import_musicxml.html')
        
        return render(request, 'admin/exercises/exercise/import_musicxml.html')

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        import_kwargs = super(ExerciseAdmin, self).get_import_resource_kwargs(
            request, *args, **kwargs
        )
        import_kwargs["request"] = request
        return import_kwargs

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(ExerciseAdmin, self).get_form(request, obj, change, **kwargs)
        form.context = {"user": request.user}
        return form

    def get_fieldsets(self, request, obj=None):
        base_fieldsets = list(super().get_fieldsets(request, obj))
        chorale = False
        if obj and isinstance(getattr(obj, "data", None), dict):
            chorale = obj.data.get("type") == ExerciseForm.TYPE_CHORALE
        elif request.method == "POST":
            chorale = request.POST.get("type") == ExerciseForm.TYPE_CHORALE
        if chorale:
            base_fieldsets.append(
                (
                    "Chorale settings",
                    {"fields": tuple(ExerciseForm.CHORALE_ONLY_FIELDS)},
                )
            )

        identification = False
        if obj and isinstance(getattr(obj, "data", None), dict):
            identification = obj.data.get("type") in (
                ExerciseForm.TYPE_IDENTIFICATION,
                ExerciseForm.TYPE_CHORALE_IDENTIFICATION,
            )
        elif request.method == "POST":
            identification = request.POST.get("type") in (
                ExerciseForm.TYPE_IDENTIFICATION,
                ExerciseForm.TYPE_CHORALE_IDENTIFICATION,
            )
        if identification:
            base_fieldsets.append(
                (
                    "Identification settings",
                    {"fields": tuple(ExerciseForm.IDENT_ONLY_FIELDS)},
                )
            )

        interval = False
        if obj and isinstance(getattr(obj, "data", None), dict):
            interval = obj.data.get("analysisType") in ("interval_generic", "interval_specific")
        elif request.method == "POST":
            # POST data doesn't carry analysisType directly; rely on obj for existing records
            pass
        if interval:
            base_fieldsets.append(
                (
                    "Interval settings",
                    {"fields": tuple(ExerciseForm.INTERVAL_ONLY_FIELDS)},
                )
            )

        return base_fieldsets

    def show_on_site(self, obj):
        if not obj.pk:
            return ""
        link = "<a href='%s' target='_blank'>Show On Site</a><br>" % obj.lab_url
        return mark_safe(link)

    show_on_site.short_description = "Link"


class PlaylistInlineAdmin(admin.TabularInline):
    model = Playlist.exercises.through
    fields = ("exercise", "order", "is_adaptive_entry")
    extra = 1



@admin.register(Playlist)
class PlaylistAdmin(DynamicArrayMixin, ImportExportModelAdmin):
    form = PlaylistForm
    list_display = ("name", "show_on_site", "authored_by", "created", "updated")
    list_filter = ("authored_by__email",)
    search_fields = (
        "name",
        "exercises",
    )
    readonly_fields = (
        "id",
        "authored_by",
        "created",
        "updated",
        "exercise_links",
        "performances",
        "transposition_matrix",
        "transposed_exercises_display",
        "show_on_site",
    )
    raw_id_fields = ("authored_by",)
    fieldsets = (
        (
            "Playlist Information",
            {
                "fields": (
                    (
                        "name",
                        "id",
                        "authored_by",
                        "show_on_site",
                        "performances",
                        "is_public",
                        "is_adaptive",
                        "is_dynamic",
                        "tags",
                        "skill_tags",
                        "min_complexity",
                        "max_complexity",
                    ),
                    # ('created', 'updated')
                ),
            },
        ),
        (
            "Transpose",
            {
                "fields": (
                    ("transposition_type", "transpose_requests"),
                    # 'transposition_matrix',
                ),
            },
        ),
        (
            "Quick Edit Access for Associated Exercises",
            {
                "fields": (
                    ("exercise_links"),
                    ("transposed_exercises_display"),
                )
            },
        ),
    )

    inlines = (PlaylistInlineAdmin,)
    save_on_top = True
    save_as = True

    resource_class = PlaylistResource

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        import_kwargs = super(PlaylistAdmin, self).get_import_resource_kwargs(
            request, *args, **kwargs
        )
        import_kwargs["request"] = request
        return import_kwargs

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(PlaylistAdmin, self).get_form(request, obj, change, **kwargs)
        form.context = {"user": request.user}
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.authored_by = request.user
        obj.save()

    def exercise_links(self, obj):
        links = ""
        for exercise in obj.exercise_objects:
            link = reverse(
                "admin:%s_%s_change" % ("exercises", "exercise"), args=(exercise._id,)
            )
            links += "<a href='%s'>%s</a><br>" % (link, exercise.id)
        return mark_safe(links)

    exercise_links.allow_tags = True
    exercise_links.short_description = "Exercise Links"

    def show_on_site(self, obj):
        if not obj.pk:
            return ""
        link = reverse("lab:playlist-view", kwargs={"playlist_id": obj.id})
        link = "<a href='%s' target='_blank'>Show On Site</a><br>" % link
        return mark_safe(link)

    show_on_site.short_description = "Link"

    def performances(self, obj):
        if not (obj and obj._id):
            return "-"
        link = reverse("lab:performance-report", kwargs={"playlist_id": obj.id})
        return mark_safe("<a href='%s'>Review Data</a><br>" % link)

    performances.allow_tags = True
    performances.short_description = "Performance Data"

    def transposed_exercises_display(self, obj):
        TRANSP_JOIN_STR = " "  # r'[,; \n]+'
        return (
            TRANSP_JOIN_STR.join(str(id_) for id_ in obj.transposed_exercises_ids)
            if obj.is_transposed()
            else ""
        )

    transposed_exercises_display.short_description = "Exercises Transposed"


@admin.register(PerformanceData)
class PerformanceDataAdmin(admin.ModelAdmin):
    form = PerformanceDataForm
    list_display = ("user", "playlist", "created", "updated")
    list_filter = ("user__email", "playlist__name")
    search_fields = ("user__email", "playlist__name")
    readonly_fields = ("created", "updated")
    raw_id_fields = ("user", "playlist")
    fieldsets = (
        ("General Info", {"fields": ("user", "playlist")}),
        ("Date Info", {"fields": ("created", "updated")}),
    )


@admin.register(Course)
class CourseAdmin(DynamicArrayMixin, ImportExportModelAdmin):
    form = CourseForm
    list_display = ("title", "show_on_site", "authored_by", "created", "updated")
    list_filter = ("authored_by__email",)
    search_fields = (
        "title",
        "exercises",
    )
    readonly_fields = (
        "id",
        "authored_by",
        "created",
        "updated",
        "playlist_links",
        "show_on_site",
    )
    raw_id_fields = ("authored_by",)
    fieldsets = (
        (
            "General Info",
            {
                "fields": (
                    ("title", "show_on_site"),
                    "id",
                    "authored_by",
                    ("created", "updated"),
                    ("adaptive_mode", "mastery_threshold"),
                    "required_skills",
                ),
            },
        ),
        ("Playlists", {"fields": ("playlist_links",)}),
    )

    save_on_top = True
    save_as = True

    resource_class = CourseResource

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        import_kwargs = super(CourseAdmin, self).get_import_resource_kwargs(
            request, *args, **kwargs
        )
        import_kwargs["request"] = request
        return import_kwargs

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(CourseAdmin, self).get_form(request, obj, change, **kwargs)
        form.context = {"user": request.user}
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.authored_by = request.user
        obj.save()

    def playlist_links(self, obj):
        links = ""
        playlists = Playlist.objects.filter(id__in=re.split(r"[,; \n]+", obj.playlists))
        for playlist in playlists:
            link = reverse(
                "admin:%s_%s_change" % ("exercises", "playlist"), args=(playlist._id,)
            )
            links += "<a href='%s'>%s</a><br>" % (link, playlist.id)
        return mark_safe(links)

    playlist_links.allow_tags = True
    playlist_links.short_description = "Playlist Links"

    def show_on_site(self, obj):
        if not obj.pk:
            return ""
        link = reverse("lab:course-view", kwargs={"course_id": obj.id})
        link = "<a href='%s' target='_blank'>Show On Site</a><br>" % link
        return mark_safe(link)

    show_on_site.short_description = "Link"


@admin.register(StudentSkillMastery)
class StudentSkillMasteryAdmin(admin.ModelAdmin):
    list_display = ("user", "skill_tag", "level", "total_attempts", "last_practiced")
    list_filter = ("level", "skill_tag", "user__email")
    search_fields = ("user__email", "skill_tag")
    readonly_fields = ("first_attempted", "last_practiced", "mastered_at")


@admin.register(SkillPrerequisite)
class SkillPrerequisiteAdmin(admin.ModelAdmin):
    list_display = ("skill_tag", "requires_tag", "course")
    list_filter = ("course", "skill_tag")
    search_fields = ("skill_tag", "requires_tag")


@admin.register(IdentificationAttempt)
class IdentificationAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "exercise", "submitted_at")
    list_filter = ("user__email", "exercise__id")
    search_fields = ("user__email", "exercise__id")
    readonly_fields = ("submitted_at",)

