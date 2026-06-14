"""Teacher library review workflow views."""

from django.conf import settings
from django.db.models import Count, Q
from django.http import Http404
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ROLE_TEACHER, User
from apps.exercises.models import Exercise, Playlist
from apps.teacher.decorators import teacher_required


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
    playlist = get_object_or_404(Playlist, id=playlist_id, authored_by=request.user)
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
