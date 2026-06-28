from django.contrib import admin
from django.db.models import Prefetch
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
from django.contrib import messages
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from import_export.admin import ImportExportModelAdmin
from django.core.management import call_command
from io import StringIO
from django.utils.html import format_html

from apps.exercises.forms import (
    ExerciseForm,
    PlaylistForm,
    PerformanceDataForm,
    CourseForm,
)
from apps.exercises.models import (
    Exercise,
    Playlist,
    ExercisePlaylistOrdered,
    PerformanceData,
    Course,
    StudentSkillMastery,
    SkillPrerequisite,
    IdentificationAttempt
)
from apps.exercises.taxonomy_reader import TaxonomyReader

import re
import sys
import os

from apps.exercises.resources import ExerciseResource, PlaylistResource, CourseResource


class ModeFilter(admin.SimpleListFilter):
    title = 'Mode'
    parameter_name = 'data__mode'
    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request).exclude(data__mode__isnull=True)
        modes = set(qs.values_list('data__mode', flat=True))
        return [(m, m) for m in sorted(list(modes)) if m]
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(data__mode=self.value())
        return queryset

class AnalysisTypeFilter(admin.SimpleListFilter):
    title = 'Analysis Type'
    parameter_name = 'data__analysisType'
    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request).exclude(data__analysisType__isnull=True)
        types = set(qs.values_list('data__analysisType', flat=True))
        return [(t, t) for t in sorted(list(types)) if t]
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(data__analysisType=self.value())
        return queryset

class SkillTagFilter(admin.SimpleListFilter):
    title = 'Skill Tag'
    parameter_name = 'skill_tag'
    def lookups(self, request, model_admin):
        from django.db.models import Func, F
        qs = model_admin.get_queryset(request).annotate(tag=Func(F('skill_tags'), function='unnest')).values_list('tag', flat=True).distinct()
        return [(t, t) for t in sorted(list(qs)) if t]
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(skill_tags__contains=[self.value()])
        return queryset



class GenerateContentAdminSite(admin.AdminSite):
    pass


def _run_command(name, stdout, **kwargs):
    out = StringIO()
    call_command(name, stdout=out, **kwargs)
    stdout.write(out.getvalue())


def _playlist_unit_num(playlist):
    tags = list(getattr(playlist, "skill_tags", []) or []) + list(getattr(playlist, "tags", []) or [])
    for tag in tags:
        if isinstance(tag, str) and tag.startswith("unit:"):
            try:
                return int(tag.split(":", 1)[1])
            except (TypeError, ValueError):
                continue
    for tag in tags:
        unit = TaxonomyReader.get_unit_for_tag(tag)
        if unit:
            try:
                return int(unit["n"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def _student_playlist_url(playlist, exercise_num=1):
    unit_num = _playlist_unit_num(playlist)
    if unit_num is None:
        return reverse("lab:playlist-view", kwargs={"playlist_id": playlist.id})
    return (
        reverse("student:player", kwargs={"unit_num": unit_num})
        + f"?playlist={playlist.id}&exercise_num={exercise_num}"
    )


_EXERCISE_PLAYLIST_ORDER = ("-playlist__is_public", "playlist__name", "order", "_id")


def _student_exercise_url(exercise):
    if "exerciseplaylistordered_set" in getattr(exercise, "_prefetched_objects_cache", {}):
        epolist = exercise._prefetched_objects_cache["exerciseplaylistordered_set"]
    else:
        epolist = (
            ExercisePlaylistOrdered.objects.filter(exercise=exercise)
            .select_related("playlist")
            .order_by(*_EXERCISE_PLAYLIST_ORDER)
        )
    for epo in epolist:
        unit_num = _playlist_unit_num(epo.playlist)
        if unit_num is None:
            continue
        return _student_playlist_url(epo.playlist, exercise_num=epo.order)
    return exercise.lab_url


@admin.register(Exercise)
class ExerciseAdmin(ImportExportModelAdmin):
    form = ExerciseForm
    list_display = (
        "id",
        "preview_mode",
        "preview_analysis_type",
        "preview_skill_tags",
        "show_on_site",
        "authored_by",
        "is_public",
        "updated",
    )
    list_filter = ("authored_by__email", "is_public", ModeFilter, AnalysisTypeFilter, SkillTagFilter)
    search_fields = ("id",)
    readonly_fields = ("id", "authored_by", "created", "updated", "show_on_site")
    raw_id_fields = ("authored_by",)
    actions = ["refresh_selected"]
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
    list_per_page = 500
    list_max_show_all = 2000

    list_select_related = ("authored_by",)

    resource_class = ExerciseResource

    change_list_template = "admin/exercises/exercise/change_list.html"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            Prefetch(
                "exerciseplaylistordered_set",
                queryset=ExercisePlaylistOrdered.objects.select_related("playlist")
                .order_by(*_EXERCISE_PLAYLIST_ORDER),
            )
        )

    def get_urls(self):
        urls = super().get_urls()
        from apps.exercises.admin_views import operations_view
        custom_urls = [
            path(
                'import-musicxml/',
                self.admin_site.admin_view(self.import_musicxml_view),
                name='exercises_exercise_import_musicxml',
            ),
            path(
                'generate-content/',
                self.admin_site.admin_view(self.generate_content_view),
                name='exercises_exercise_generate_content',
            ),
            path(
                'operations/',
                self.admin_site.admin_view(operations_view),
                name='exercises_exercise_operations',
            ),
        ]
        return custom_urls + urls

    def generate_content_view(self, request):
        if request.method == "POST":
            command = request.POST.get("command")
            author = request.POST.get("author", "").strip()
            is_public = True

            if not author:
                messages.error(request, "Author email is required.")
                return render(request, "admin/exercises/exercise/generate_content.html")

            out = StringIO()
            try:
                if command == "generate_unit1":
                    call_command("generate_unit1", author=author, stdout=out)
                    messages.success(request, f"Unit 1 generated.\n{out.getvalue()}")

                elif command == "generate_unit1_playlist_only":
                    call_command("generate_unit1", author=author, playlist_only=True, stdout=out)
                    messages.success(request, f"Unit 1 playlists rebuilt from existing exercises.\n{out.getvalue()}")

                elif command == "generate_unit2_meter_exercises":
                    call_command("generate_unit2_meter_exercises", author=author, public=is_public, stdout=out)
                    messages.success(request, f"Unit 2 meter exercises generated.\n{out.getvalue()}")

                elif command == "generate_unit2_barline_exercises":
                    count = int(request.POST.get("barline_count") or 1)
                    meter = request.POST.get("barline_meter", "3/4").strip() or "3/4"
                    measures = int(request.POST.get("barline_measures") or 2)
                    pitch_mode = (
                        request.POST.get("barline_pitch_mode", "rhythm_only").strip()
                        or "rhythm_only"
                    )
                    call_command(
                        "generate_unit2_barline_exercises",
                        author=author,
                        public=is_public,
                        count=count,
                        meter=meter,
                        measures=measures,
                        pitch_mode=pitch_mode,
                        source="manual",
                        stdout=out,
                    )
                    messages.success(request, f"Unit 2 add-barlines exercises generated.\n{out.getvalue()}")

                elif command == "generate_unit2_barline_exercises_corpus":
                    level_raw = request.POST.get("corpus_level", "").strip()
                    limit_raw = request.POST.get("corpus_limit", "").strip()
                    kwargs = dict(author=author, public=is_public, source="corpus", stdout=out)
                    if level_raw:
                        kwargs["level"] = int(level_raw)
                    if limit_raw:
                        kwargs["limit"] = int(limit_raw)
                    call_command("generate_unit2_barline_exercises", **kwargs)
                    messages.success(request, f"Unit 2 corpus barline exercises generated.\n{out.getvalue()}")

                elif command in ("generate_unit3_key_sig_exercises", "generate_unit3_scale_exercises", "generate_unit3_both"):
                    run_key_sig = command in ("generate_unit3_key_sig_exercises", "generate_unit3_both")
                    run_scales  = command in ("generate_unit3_scale_exercises",  "generate_unit3_both")
                    if run_key_sig:
                        call_command("generate_unit3_key_sig_exercises", author=author, public=is_public, overwrite=True, stdout=out)
                    if run_scales:
                        call_command("generate_unit3_scale_exercises", author=author, public=is_public, overwrite=True, stdout=out)
                    messages.success(request, f"Unit 3 content generated.\n{out.getvalue()}")

                elif command in ("create_unit_playlist", "create_unit_playlist_only"):
                    unit = request.POST.get("unit", "").strip()
                    riemenschneider = request.POST.get("riemenschneider", "").strip()
                    mode = request.POST.get("mode", "roman").strip()
                    overwrite = request.POST.get("overwrite") == "on"
                    if not unit or not riemenschneider:
                        messages.error(request, "Unit and Riemenschneider range are required.")
                        return render(request, "admin/exercises/exercise/generate_content.html")
                    playlist_only = (command == "create_unit_playlist_only")
                    call_command(
                        "create_unit_playlist",
                        unit=int(unit),
                        riemenschneider=riemenschneider,
                        author=author,
                        mode=mode,
                        public=is_public,
                        playlist_only=playlist_only,
                        overwrite=overwrite,
                        stdout=out,
                    )
                    label = "playlist rebuilt from existing exercises" if playlist_only else "exercises imported and playlist created"
                    messages.success(request, f"Unit {unit} {label}.\n{out.getvalue()}")

                else:
                    messages.error(request, f"Unknown command: {command}")

            except Exception as e:
                details = out.getvalue().strip()
                if details:
                    messages.error(request, f"Error running {command}: {e}\n\nPartial output:\n{details}")
                else:
                    messages.error(request, f"Error running {command}: {e}")

            return redirect("admin:exercises_exercise_generate_content")

        return render(request, "admin/exercises/exercise/generate_content.html", {
            "title": "Generate Content",
        })

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
        link = "<a href='%s' target='_blank'>Show On Site</a><br>" % _student_exercise_url(obj)
        return mark_safe(link)

    show_on_site.short_description = "Link"

    def preview_mode(self, obj):
        return obj.data.get('mode') if obj.data else None
    preview_mode.short_description = 'Mode'

    def preview_analysis_type(self, obj):
        return obj.data.get('analysisType') if obj.data else None
    preview_analysis_type.short_description = 'Analysis Type'

    def preview_skill_tags(self, obj):
        if not obj.skill_tags: return ""
        chips = [f"<span style='display:inline-block; padding:2px 6px; margin:2px; background-color:#e0e0e0; border-radius:12px; font-size:11px;'>{t}</span>" for t in obj.skill_tags]
        return format_html("".join(chips))
    preview_skill_tags.short_description = 'Skill Tags'
    
    def refresh_selected(self, request, queryset):
        tags = set()
        for obj in queryset:
            if obj.skill_tags:
                tags.update(obj.skill_tags)
        
        if not tags:
            self.message_user(request, "No skill tags found in selected exercises.", level='warning')
            return
            
        out = StringIO()
        for tag in tags:
            try:
                call_command('recompute_chorale_analysis', tag=tag, stdout=out)
                call_command('recompute_harmonization_targets', tag=tag, stdout=out)
            except Exception as e:
                self.message_user(request, f"Error refreshing tag {tag}: {e}", level='error')
                return
        self.message_user(request, f"Successfully refreshed for tags: {', '.join(tags)}", level='success')
    refresh_selected.short_description = "Refresh selected (runs recompute commands scoped to their tags)"


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
                        "feedback_mode",
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
        link = _student_playlist_url(obj)
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
