"""Views for the teacher course creation wizard."""
import json
from datetime import datetime, time

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Group
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered
from apps.exercises.taxonomy_reader import TaxonomyReader
from apps.teacher.decorators import teacher_required


def _get_factory_user():
    """Return the factory account User or None if not configured / not found."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    email = getattr(settings, "FACTORY_USER_EMAIL", None)
    if not email:
        return None
    return User.objects.filter(email=email).first()


def _mode_from_tags(skill_tags: list, name: str) -> str:
    """Derive mode string from a playlist's skill_tags or fall back to name-based heuristic."""
    for tag in skill_tags:
        if tag.startswith("mode:"):
            return tag[len("mode:"):]
    name_lower = name.lower()
    if "roman" in name_lower:
        return "roman"
    if "figure" in name_lower:
        return "figures"
    if "play" in name_lower:
        return "play"
    return "other"


def _build_units_json(factory_user) -> str:
    """Return a JSON string of branch→tier→unit objects with attached playlists.

    Each unit looks like:
      {"branch": str, "tier": str, "n": int, "title": str,
       "playlists": [{"id": str, "name": str, "mode": str}]}
    """
    branches = TaxonomyReader.get_branches()
    result = []

    for branch in branches:
        branch_name = branch.get("name", "")
        for tier in branch.get("tiers", []):
            tier_name = tier.get("name", "")
            for unit in tier.get("units", []):
                unit_n = unit.get("n")
                unit_title = unit.get("title", f"Unit {unit_n}")

                playlists = []
                if factory_user is not None:
                    qs = Playlist.objects.filter(
                        authored_by=factory_user,
                        skill_tags__contains=[f"unit:{unit_n}"],
                    )
                    for pl in qs:
                        playlists.append({
                            "id": pl.id,
                            "name": pl.name,
                            "mode": _mode_from_tags(pl.skill_tags or [], pl.name),
                        })

                result.append({
                    "branch": branch_name,
                    "tier": tier_name,
                    "n": unit_n,
                    "title": unit_title,
                    "playlists": playlists,
                })

    return json.dumps(result)


@teacher_required
def wizard_view(request):
    """GET: render the course creation wizard."""
    factory_user = _get_factory_user()
    factory_available = factory_user is not None

    units_json = _build_units_json(factory_user)

    return render(
        request,
        "teacher/course_wizard.html",
        {
            "units_json": units_json,
            "factory_available": factory_available,
        },
    )


def _parse_date(value: str) -> datetime.date:
    """Parse an ISO date string; raise ValueError on failure."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"Invalid date: {value!r}")


@teacher_required
@require_http_methods(["POST"])
def create_course_view(request):
    """POST JSON → create Course + optional Group + PlaylistCourseOrdered rows.

    Returns 201 {"courseId": "..."} or 400 {"error": "..."}.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    title = (body.get("title") or "").strip()
    if not title or len(title) > 64:
        return JsonResponse(
            {"error": "title must be a non-empty string of at most 64 characters."},
            status=400,
        )

    try:
        start_date = _parse_date(body.get("start"))
        end_date = _parse_date(body.get("end"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if start_date >= end_date:
        return JsonResponse({"error": "start must be before end."}, status=400)

    group_name = (body.get("groupName") or "").strip() or None

    units_data = body.get("units")
    if not units_data or not isinstance(units_data, list):
        return JsonResponse({"error": "units must be a non-empty list."}, status=400)

    # Validate all playlist IDs before touching the DB
    all_playlist_ids = []
    for unit_item in units_data:
        for pid in unit_item.get("playlistIds", []):
            all_playlist_ids.append(pid)

    if all_playlist_ids:
        existing_ids = set(
            Playlist.objects.filter(id__in=all_playlist_ids).values_list("id", flat=True)
        )
        for pid in all_playlist_ids:
            if pid not in existing_ids:
                return JsonResponse(
                    {"error": f"Playlist {pid!r} does not exist."}, status=400
                )

    # Parse per-unit publish/due dates upfront
    parsed_units = []
    for unit_item in units_data:
        try:
            publish_date = _parse_date(unit_item.get("publish"))
            due_date = _parse_date(unit_item.get("due"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        parsed_units.append({
            "unit": unit_item.get("unit"),
            "playlistIds": unit_item.get("playlistIds", []),
            "publish": publish_date,
            "due": due_date,
        })

    tz = timezone.get_current_timezone()

    with transaction.atomic():
        course = Course(
            title=title,
            authored_by=request.user,
            open=False,
            start_date=start_date,
            end_date=end_date,
        )
        course.save()

        if group_name:
            group = Group(name=group_name, manager=request.user)
            group.save()
            course.visible_to.add(group)

        order = 1
        for unit_item in parsed_units:
            publish_dt = timezone.make_aware(
                datetime.combine(unit_item["publish"], time(0, 0, 0)), tz
            )
            due_dt = timezone.make_aware(
                datetime.combine(unit_item["due"], time(23, 59, 0)), tz
            )
            for pid in unit_item["playlistIds"]:
                playlist = Playlist.objects.get(id=pid)
                PlaylistCourseOrdered.objects.create(
                    course=course,
                    playlist=playlist,
                    order=order,
                    publish_date=publish_dt,
                    due_date=due_dt,
                )
                order += 1

    return JsonResponse({"courseId": course.id}, status=201)
