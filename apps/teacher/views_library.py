"""Teacher library review workflow views."""

import json

from django.conf import settings
from django.db.models import Count, Q
from django.http import Http404
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ROLE_TEACHER, User
from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.teacher.decorators import teacher_required


ANALYSIS_TYPE_CHOICES = [
    ("roman", "Roman numeral"),
    ("figured_bass", "Figured bass"),
    ("figured_bass_unabbreviated", "Figured bass (unabbreviated)"),
    ("scale_degree", "Scale degree"),
    ("note_name", "Note name"),
    ("solfege", "Solfege"),
    ("do_based_solfege", "Do-based solfege"),
    ("fixed_do", "Fixed do"),
    ("pitch_class", "Pitch class"),
    ("set_class_prime", "Set class - prime form"),
    ("set_class_forte", "Set class - Forte label"),
    ("set_class_normal", "Set class - normal order"),
    ("set_class_set", "Set class - set notation"),
    ("spacing", "Spacing"),
    ("interval_generic", "Interval (generic)"),
    ("interval_specific", "Interval (specific)"),
]


def _factory_user():
    email = settings.FACTORY_USER_EMAIL
    user, _created = User.objects.get_or_create(
        email=email,
        defaults={
            "is_active": True,
            "role": ROLE_TEACHER,
        },
    )
    return user


def _bad_request(message):
    return JsonResponse({"ok": False, "error": message}, status=400)


def _ok(**payload):
    return JsonResponse({"ok": True, **payload})


def _require_superuser(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Superuser required")
    return None


def _submit_for_review(obj):
    if not obj.is_public:
        return _bad_request("Only public content can be submitted for official review.")
    if obj.official_review_status in {
        Exercise.REVIEW_PENDING,
        Exercise.REVIEW_APPROVED,
    }:
        return _bad_request("Content is already submitted or approved.")

    obj.official_review_status = Exercise.REVIEW_PENDING
    obj.save(update_fields=["official_review_status"])
    return _ok(official_review_status=obj.official_review_status)


def _approve(obj):
    factory_user = _factory_user()
    obj.is_official = True
    obj.official_review_status = Exercise.REVIEW_APPROVED
    obj.authored_by = factory_user
    obj.save(update_fields=["is_official", "official_review_status", "authored_by"])
    return _ok(official_review_status=obj.official_review_status)


def _reject(obj):
    obj.official_review_status = Exercise.REVIEW_NONE
    obj.save(update_fields=["official_review_status"])
    return _ok(official_review_status=obj.official_review_status)


@require_POST
@teacher_required
def playlist_submit_review_view(request, playlist_id):
    playlist = _get_editable_playlist(request, playlist_id)
    return _submit_for_review(playlist)


@require_POST
@teacher_required
def playlist_approve_view(request, playlist_id):
    forbidden = _require_superuser(request)
    if forbidden:
        return forbidden

    playlist = get_object_or_404(Playlist, id=playlist_id)
    return _approve(playlist)


@require_POST
@teacher_required
def playlist_reject_view(request, playlist_id):
    forbidden = _require_superuser(request)
    if forbidden:
        return forbidden

    playlist = get_object_or_404(Playlist, id=playlist_id)
    return _reject(playlist)


@require_POST
@teacher_required
def exercise_submit_review_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id, authored_by=request.user)
    return _submit_for_review(exercise)


@require_POST
@teacher_required
def exercise_approve_view(request, exercise_id):
    forbidden = _require_superuser(request)
    if forbidden:
        return forbidden

    exercise = get_object_or_404(Exercise, id=exercise_id)
    return _approve(exercise)


@require_POST
@teacher_required
def exercise_reject_view(request, exercise_id):
    forbidden = _require_superuser(request)
    if forbidden:
        return forbidden

    exercise = get_object_or_404(Exercise, id=exercise_id)
    return _reject(exercise)


def _visible_playlists(user):
    return Playlist.objects.filter(
        Q(authored_by=user) | Q(is_public=True) | Q(is_official=True)
    )


def _visible_exercises(user):
    return Exercise.objects.filter(
        Q(authored_by=user) | Q(is_public=True) | Q(is_official=True)
    )


def _get_editable_playlist(request, playlist_id):
    """Look up a playlist for a mutating action, matching the same
    author-or-superuser rule the playlist editor template uses to decide
    whether to show edit controls (see can_edit in playlist_detail_view)."""
    if request.user.is_superuser:
        return get_object_or_404(Playlist, id=playlist_id)
    return get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)


@teacher_required
def library_hub_view(request):
    tab = request.GET.get("tab", "playlists")
    if tab not in {"playlists", "exercises", "official"}:
        tab = "playlists"
    if tab == "official" and not request.user.is_superuser:
        return HttpResponseForbidden("Superuser required")

    unit_filter = request.GET.get("unit", "").strip()
    official_filter = request.GET.get("official", "").strip()

    playlists_qs = _visible_playlists(request.user).order_by("-updated")
    exercises_qs = _visible_exercises(request.user).order_by("-updated")
    if unit_filter:
        unit_tag = f"unit:{unit_filter}"
        playlists_qs = playlists_qs.filter(skill_tags__contains=[unit_tag])
        exercises_qs = exercises_qs.filter(skill_tags__contains=[unit_tag])
    if official_filter == "official":
        playlists_qs = playlists_qs.filter(is_official=True)
        exercises_qs = exercises_qs.filter(is_official=True)
    elif official_filter == "personal":
        playlists_qs = playlists_qs.filter(authored_by=request.user)
        exercises_qs = exercises_qs.filter(authored_by=request.user)

    pending_playlists = []
    pending_exercises = []
    if request.user.is_superuser:
        pending_playlists = list(
            Playlist.objects.filter(
                official_review_status=Exercise.REVIEW_PENDING
            ).order_by("-updated")
        )
        pending_exercises = list(
            Exercise.objects.filter(
                official_review_status=Exercise.REVIEW_PENDING
            ).order_by("-updated")
        )

    return render(
        request,
        "teacher/library_hub.html",
        {
            "tab": tab,
            "playlists": list(playlists_qs.annotate(exercise_count=Count("exercises"))[:200]),
            "exercises": list(exercises_qs[:200]),
            "pending_playlists": pending_playlists,
            "pending_exercises": pending_exercises,
            "pending_count": len(pending_playlists) + len(pending_exercises),
            "unit_filter": unit_filter,
            "official_filter": official_filter,
        },
    )


@teacher_required
def exercise_preview_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id)
    if not (
        exercise.is_public
        or exercise.is_official
        or exercise.authored_by_id == request.user.pk
    ):
        raise Http404

    score_data = exercise.data.get("score") if isinstance(exercise.data, dict) else None
    return JsonResponse({"score_data": score_data})


@teacher_required
def exercises_search_view(request):
    query = request.GET.get("q", "").strip()
    unit = request.GET.get("unit", "").strip()
    queryset = _visible_exercises(request.user).order_by("-updated")
    if query:
        queryset = queryset.filter(description__icontains=query)
    if unit:
        queryset = queryset.filter(skill_tags__contains=[f"unit:{unit}"])

    results = [
        {
            "id": exercise.id,
            "description": exercise.description or "",
            "complexity": exercise.complexity,
            "is_official": exercise.is_official,
        }
        for exercise in queryset[:50]
    ]
    return JsonResponse({"results": results})


@teacher_required
def playlist_detail_view(request, playlist_id):
    playlist = get_object_or_404(
        Playlist,
        Q(id=playlist_id)
        & (Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)),
    )
    ordered_exercises = (
        ExercisePlaylistOrdered.objects.filter(playlist=playlist)
        .select_related("exercise")
        .order_by("order", "pk")
    )
    exercises_data = [
        {
            "id": ordered.exercise.id,
            "description": ordered.exercise.description or "",
            "complexity": ordered.exercise.complexity,
            "skill_tags": ordered.exercise.skill_tags or [],
            "is_official": ordered.exercise.is_official,
            "epo_id": ordered.pk,
            "order": ordered.order,
        }
        for ordered in ordered_exercises
    ]

    return render(
        request,
        "teacher/playlist_editor.html",
        {
            "playlist": playlist,
            "ordered_exercises": ordered_exercises,
            "exercises_json": json.dumps(exercises_data),
            "can_edit": playlist.authored_by_id == request.user.pk
            or request.user.is_superuser,
            "review_status": playlist.official_review_status,
        },
    )


@teacher_required
@require_POST
def playlist_save_view(request, playlist_id):
    playlist = _get_editable_playlist(request, playlist_id)
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "name" in body:
        playlist.name = str(body["name"])[:64]
    if "skill_tags" in body and isinstance(body["skill_tags"], list):
        playlist.skill_tags = [str(tag)[:64] for tag in body["skill_tags"]]
    if "is_public" in body:
        playlist.is_public = bool(body["is_public"])
    playlist.save()
    return _ok()


@teacher_required
@require_POST
def playlist_reorder_view(request, playlist_id):
    playlist = _get_editable_playlist(request, playlist_id)
    try:
        body = json.loads(request.body or "{}")
        order = body["order"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "order list required"}, status=400)
    if not isinstance(order, list):
        return JsonResponse({"error": "order list required"}, status=400)

    for index, ordered_pk in enumerate(order):
        ExercisePlaylistOrdered.objects.filter(
            pk=ordered_pk,
            playlist=playlist,
        ).update(order=index)
    return _ok()


@teacher_required
@require_POST
def playlist_add_exercise_view(request, playlist_id):
    playlist = _get_editable_playlist(request, playlist_id)
    try:
        body = json.loads(request.body or "{}")
        exercise_id = body["exerciseId"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "exerciseId required"}, status=400)

    exercise = get_object_or_404(
        Exercise,
        Q(id=exercise_id)
        & (Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)),
    )
    next_order = ExercisePlaylistOrdered.objects.filter(playlist=playlist).count()
    ordered = ExercisePlaylistOrdered.objects.create(
        playlist=playlist,
        exercise=exercise,
        order=next_order,
    )
    return _ok(epoId=ordered.pk)


@teacher_required
@require_POST
def playlist_remove_exercise_view(request, playlist_id, ordered_id):
    playlist = _get_editable_playlist(request, playlist_id)
    ordered = get_object_or_404(
        ExercisePlaylistOrdered,
        pk=ordered_id,
        playlist=playlist,
    )
    ordered.delete()
    return _ok()


@teacher_required
def exercise_detail_view(request, exercise_id):
    exercise = get_object_or_404(
        Exercise,
        Q(id=exercise_id)
        & (Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)),
    )
    can_edit = exercise.authored_by_id == request.user.pk or request.user.is_superuser
    analysis_type = "roman"
    umto_meta = {}
    if isinstance(exercise.data, dict):
        analysis_type = exercise.data.get("analysisType", "roman")
        score = exercise.data.get("score", {})
        umto_block = score.get("umto", {}) if isinstance(score, dict) else {}
        meta = umto_block.get("metadata", {}) if isinstance(umto_block, dict) else {}
        umto_meta = {
            "key": meta.get("key", ""),
            "meter": meta.get("meter", ""),
            "mode": meta.get("mode", ""),
            "score_kind": meta.get("score_kind", ""),
            "input_style": meta.get("input_style", ""),
            "analysis_review_status": meta.get("analysis_review_status", "none"),
            "complexity_score": meta.get("complexity_score", 1),
        }

    in_playlists = list(
        Playlist.objects.filter(exercises=exercise)
        .values("id", "name", "is_official")[:20]
    )
    return render(
        request,
        "teacher/exercise_editor.html",
        {
            "exercise": exercise,
            "umto_meta": umto_meta,
            "in_playlists": in_playlists,
            "can_edit": can_edit,
            "analysis_type": analysis_type,
            "analysis_type_choices": ANALYSIS_TYPE_CHOICES,
            "review_status": exercise.official_review_status,
        },
    )


@teacher_required
@require_POST
def exercise_save_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id, authored_by=request.user)
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "description" in body:
        exercise.description = str(body["description"])[:60]
    if "skill_tags" in body and isinstance(body["skill_tags"], list):
        exercise.skill_tags = [str(tag)[:64] for tag in body["skill_tags"]]
    if "complexity" in body:
        try:
            exercise.complexity = max(1, min(20, int(body["complexity"])))
        except (TypeError, ValueError):
            pass
    if "is_public" in body:
        exercise.is_public = bool(body["is_public"])
    if "analysisType" in body and isinstance(exercise.data, dict):
        exercise.data = {
            **exercise.data,
            "analysisType": str(body["analysisType"]),
        }
    exercise.save()
    return _ok()
