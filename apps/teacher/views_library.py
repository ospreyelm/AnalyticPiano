"""Teacher library review workflow views."""

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
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
