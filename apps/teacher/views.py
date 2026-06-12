"""Views for the teacher course creation wizard."""
import json
import logging
from datetime import datetime, time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import Group
from apps.exercises.models import Course, Playlist, PlaylistCourseOrdered
from apps.exercises.taxonomy_reader import TaxonomyReader
from apps.teacher.decorators import teacher_required

logger = logging.getLogger(__name__)


def _serialize_course_groups(course):
    """Return a list of group dicts for the given course's visible_to groups."""
    result = []
    for group in course.visible_to.prefetch_related("members").all():
        members = [
            {"name": m.get_full_name(), "email": m.email}
            for m in group.members.all()
        ]
        result.append({
            "name": group.name,
            "join_code": group.join_code,
            "member_count": len(members),
            "members": members,
        })
    return result


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


# ---------------------------------------------------------------------------
# Course management views (Task 1)
# ---------------------------------------------------------------------------

@teacher_required
def course_list_view(request):
    """GET /teacher/courses/ — list teacher's courses."""
    from django.db.models import Count

    courses_qs = Course.objects.filter(authored_by=request.user).prefetch_related(
        "visible_to__members",
        "playlists",
    ).order_by("-created")

    courses = []
    for course in courses_qs:
        unit_count = PlaylistCourseOrdered.objects.filter(course=course).count()
        student_ids = set()
        for group in course.visible_to.all():
            for member in group.members.all():
                student_ids.add(member.pk)
        courses.append({
            "id": course.id,
            "title": course.title,
            "start_date": course.start_date,
            "end_date": course.end_date,
            "unit_count": unit_count,
            "student_count": len(student_ids),
        })

    return render(request, "teacher/course_list.html", {"courses": courses})


@teacher_required
def course_detail_view(request, course_id):
    """GET /teacher/courses/<course_id>/ — course detail."""
    from django.shortcuts import get_object_or_404
    from django.db.models import Q

    course = get_object_or_404(Course, id=course_id, authored_by=request.user)

    # Build PCO rows JSON
    pco_qs = (
        PlaylistCourseOrdered.objects.filter(course=course)
        .select_related("playlist")
        .order_by("order")
    )
    tz = timezone.get_current_timezone()
    pco_rows = []
    for pco in pco_qs:
        publish_iso = None
        due_iso = None
        if pco.publish_date:
            publish_iso = pco.publish_date.astimezone(tz).date().isoformat()
        if pco.due_date:
            due_iso = pco.due_date.astimezone(tz).date().isoformat()
        pco_rows.append({
            "pcoId": pco.pk,
            "playlistId": pco.playlist.id,
            "playlistName": pco.playlist.name,
            "mode": _mode_from_tags(pco.playlist.skill_tags or [], pco.playlist.name),
            "skillTags": pco.playlist.skill_tags or [],
            "publish": publish_iso,
            "due": due_iso,
            "order": pco.order,
        })

    # Build groups data
    groups = _serialize_course_groups(course)

    # Build addable playlists
    playlist_filter = Q(authored_by=request.user) | Q(is_public=True) | Q(is_official=True)
    addable_qs = (
        Playlist.objects.filter(playlist_filter)
        .order_by("name")[:500]
    )
    addable_playlists = []
    for pl in addable_qs:
        if pl.authored_by_id == request.user.pk:
            source = "mine"
        else:
            source = "official" if pl.is_official else "mine"
        addable_playlists.append({"id": pl.id, "name": pl.name, "source": source})

    # Dashboard deep-link URLs
    from django.urls import reverse
    dashboard_edit_url = reverse("dashboard:edit-course", args=[course.id])
    dashboard_activity_url = reverse("dashboard:course-activity", args=[course.id])

    return render(
        request,
        "teacher/course_detail.html",
        {
            "course": course,
            "pco_rows_json": json.dumps(pco_rows),
            "groups_json": json.dumps(groups),
            "activity_json": json.dumps(course.performance_dict),
            "addable_playlists_json": json.dumps(addable_playlists),
            "dashboard_edit_url": dashboard_edit_url,
            "dashboard_activity_url": dashboard_activity_url,
        },
    )


@teacher_required
@require_http_methods(["POST"])
def update_pco_view(request, course_id):
    """POST /teacher/courses/<course_id>/update-pco/ — update/remove PCO rows."""
    from django.shortcuts import get_object_or_404

    course = get_object_or_404(Course, id=course_id, authored_by=request.user)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    changes = body.get("changes", [])
    removals = body.get("removals", [])

    # Validate all pcoIds belong to this course
    all_pco_ids = [c["pcoId"] for c in changes if "pcoId" in c] + list(removals)
    if all_pco_ids:
        course_pco_ids = set(
            PlaylistCourseOrdered.objects.filter(course=course)
            .values_list("pk", flat=True)
        )
        for pid in all_pco_ids:
            if pid not in course_pco_ids:
                return JsonResponse(
                    {"error": f"PCO {pid} does not belong to this course."}, status=400
                )

    tz = timezone.get_current_timezone()

    with transaction.atomic():
        # Apply changes
        for change in changes:
            pco_id = change.get("pcoId")
            if pco_id is None:
                continue
            try:
                pco = PlaylistCourseOrdered.objects.get(pk=pco_id, course=course)
            except PlaylistCourseOrdered.DoesNotExist:
                return JsonResponse({"error": f"PCO {pco_id} not found."}, status=400)

            if "publish" in change:
                if change["publish"] is None:
                    pco.publish_date = None
                else:
                    try:
                        d = _parse_date(change["publish"])
                    except ValueError as exc:
                        return JsonResponse({"error": str(exc)}, status=400)
                    pco.publish_date = timezone.make_aware(
                        datetime.combine(d, time(0, 0, 0)), tz
                    )

            if "due" in change:
                if change["due"] is None:
                    pco.due_date = None
                else:
                    try:
                        d = _parse_date(change["due"])
                    except ValueError as exc:
                        return JsonResponse({"error": str(exc)}, status=400)
                    pco.due_date = timezone.make_aware(
                        datetime.combine(d, time(23, 59, 0)), tz
                    )

            if "order" in change and change["order"] is not None:
                pco.order = change["order"]

            pco.save()

        # Apply removals
        for pco_id in removals:
            PlaylistCourseOrdered.objects.filter(pk=pco_id, course=course).delete()

    return JsonResponse({"ok": True})


@teacher_required
@require_http_methods(["POST"])
def respread_view(request, course_id):
    """POST /teacher/courses/<course_id>/respread/ — re-spread publish/due dates."""
    from django.shortcuts import get_object_or_404
    from apps.teacher.scheduling import spread_schedule
    import datetime as dt

    course = get_object_or_404(Course, id=course_id, authored_by=request.user)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    from_order = body.get("fromOrder", 1)
    publish_all_at_start = bool(body.get("publishAllAtStart", False))

    if not course.end_date:
        return JsonResponse({"error": "Course has no end_date."}, status=400)

    rows = list(
        PlaylistCourseOrdered.objects.filter(course=course, order__gte=from_order)
        .order_by("order")
    )

    if not rows:
        return JsonResponse({"error": "No PCO rows at or after fromOrder."}, status=400)

    today = dt.date.today()
    window_start = max(today, course.start_date) if course.start_date else today
    window_end = course.end_date

    if window_start >= window_end:
        return JsonResponse({"error": "window start >= end_date."}, status=400)

    windows = spread_schedule(
        window_start,
        window_end,
        n_units=len(rows),
        publish_all_at_start=publish_all_at_start,
    )

    tz = timezone.get_current_timezone()
    with transaction.atomic():
        for pco, win in zip(rows, windows):
            pco.publish_date = timezone.make_aware(
                datetime.combine(win.publish_date, time(0, 0, 0)), tz
            )
            pco.due_date = timezone.make_aware(
                datetime.combine(win.due_date, time(23, 59, 0)), tz
            )
            pco.save(update_fields=["publish_date", "due_date"])

    return JsonResponse({"ok": True})


@teacher_required
@require_http_methods(["POST"])
def add_group_view(request, course_id):
    """POST /teacher/courses/<course_id>/groups/ — create a new group and link to course."""
    course = get_object_or_404(Course, id=course_id, authored_by=request.user)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required."}, status=400)
    if len(name) > 100:
        return JsonResponse({"error": "name must be at most 100 characters."}, status=400)

    with transaction.atomic():
        group = Group(name=name, manager=request.user)
        group.save()
        course.visible_to.add(group)

    # Return groups in the same shape as groups_json context variable
    return JsonResponse({"groups": _serialize_course_groups(course)}, status=201)


@teacher_required
@require_http_methods(["POST"])
def add_playlist_view(request, course_id):
    """POST /teacher/courses/<course_id>/add-playlist/ — append a playlist to course."""
    from django.db.models import Max

    course = get_object_or_404(Course, id=course_id, authored_by=request.user)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    playlist_id = body.get("playlistId")
    if not playlist_id:
        return JsonResponse({"error": "playlistId is required."}, status=400)

    try:
        playlist = Playlist.objects.get(id=playlist_id)
    except Playlist.DoesNotExist:
        return JsonResponse({"error": f"Playlist {playlist_id!r} does not exist."}, status=400)

    factory_user = _get_factory_user()
    is_allowed = (
        playlist.authored_by_id == request.user.pk
        or playlist.is_public
        or (factory_user is not None and playlist.authored_by_id == factory_user.pk)
    )
    if not is_allowed:
        return JsonResponse({"error": "You do not have access to this playlist."}, status=400)

    publish_date = None
    due_date = None
    tz = timezone.get_current_timezone()

    if body.get("publish"):
        try:
            d = _parse_date(body["publish"])
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        publish_date = timezone.make_aware(datetime.combine(d, time(0, 0, 0)), tz)

    if body.get("due"):
        try:
            d = _parse_date(body["due"])
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        due_date = timezone.make_aware(datetime.combine(d, time(23, 59, 0)), tz)

    max_order = PlaylistCourseOrdered.objects.filter(course=course).aggregate(
        max_order=Max("order")
    )["max_order"] or 0
    next_order = max_order + 1

    pco = PlaylistCourseOrdered.objects.create(
        course=course,
        playlist=playlist,
        order=next_order,
        publish_date=publish_date,
        due_date=due_date,
    )

    return JsonResponse({"ok": True, "pcoId": pco.pk, "order": pco.order}, status=201)


# ---------------------------------------------------------------------------
# Unit suggestion API (Task 2.5+2.6)
# ---------------------------------------------------------------------------

@teacher_required
@require_http_methods(["POST"])
def suggest_units_view(request):
    """
    POST /teacher/play/api/suggest-units/

    Accepts a CIR score or an existing exercise ID, detects skill tags,
    and returns ranked unit suggestions for the teacher.

    Request body (JSON):
      { "exercise_id": "EA0001" }
      OR
      { "cir_score": { ...CIR dict... }, "key": "jC_" }

    Response:
      { "skill_tags": [...], "suggested_units": [9, 11] }

    Returns 200 OK with empty lists on any analysis failure (graceful degradation).
    Requires staff or superuser. Returns 403 if non-staff.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Permission denied."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"skill_tags": [], "suggested_units": []},
            status=200
        )

    detected_tags = []
    music21_score = None

    # Try to load from exercise_id first
    exercise_id = body.get("exercise_id")
    if exercise_id:
        try:
            from apps.exercises.models import Exercise
            exercise = Exercise.objects.get(id=exercise_id)

            # If exercise already has skill_tags, use them directly
            if exercise.skill_tags:
                detected_tags = exercise.skill_tags
            else:
                # Try to rebuild from the exercise data
                from apps.exercises.utils.music21_builder import build_score_from_data

                try:
                    music21_score = build_score_from_data(exercise.data)
                    chunk_key = exercise.data.get("meta", {}).get("key", "jC_")
                except Exception:
                    # If we can't build the score, gracefully return empty
                    pass

        except Exception:
            # Exercise not found or other error — gracefully continue
            pass

    # Otherwise, try to build from cir_score + key
    if not detected_tags and not music21_score:
        cir_score = body.get("cir_score")
        if cir_score and isinstance(cir_score, dict):
            try:
                from apps.exercises.utils.music21_builder import build_score_from_data

                # Wrap the cir_score in the expected data structure
                wrapped_data = {"score": cir_score}
                music21_score = build_score_from_data(wrapped_data)
                chunk_key = body.get("key", "jC_")
            except Exception:
                # Score building failed — gracefully return empty
                pass

    # If we have a music21 score, analyze it for skills
    if music21_score and not detected_tags:
        try:
            from apps.exercises.utils.skills_analyzer import analyze_chunk_skills

            chunk_key = body.get("key", "jC_")
            skills_list, complexity = analyze_chunk_skills(
                music21_score,
                chunk_key,
                description=None
            )
            detected_tags = skills_list
        except Exception:
            # Skill analysis failed — gracefully return empty
            pass

    # Suggest units from detected tags
    suggested_units = []
    if detected_tags:
        try:
            from apps.exercises.services.unit_suggester import suggest_units_from_tags

            suggested_units = suggest_units_from_tags(detected_tags, top_n=5)
        except Exception:
            # Unit suggestion failed — return empty list
            pass

    return JsonResponse(
        {
            "skill_tags": detected_tags,
            "suggested_units": suggested_units,
        },
        status=200
    )


@require_POST
@login_required
def generation_manifest_dry_run_view(request):
    """POST /teacher/play/api/generate-manifest/dry-run/

    Accepts a JSON body matching GenerationManifest fields and returns a
    dry-run estimate of exercises that would be created.

    Request body (JSON):
      {
        "source": "bach_riemenschneider" | "played_in",
        "source_ref": "1-30" | "exercise_id",
        "unit": 9,
        "skill_tags": [],
        "exercise_types": ["play", "roman"],
        "key_set": ["C", "G"],
        "playlist_target": null,
        "is_official": false,
        "author_email": "teacher@example.com"
      }

    Response:
      {
        "source": "bach_riemenschneider",
        "source_ref": "1-30",
        "unit": 9,
        "exercise_types": ["play", "roman"],
        "key_count": 2,
        "estimated_exercises": 4,
        "is_official": false,
        "playlist_target": null
      }

    Requires staff or superuser. Returns 403 if non-staff.
    is_official=True requires superuser. Returns 403 if non-superuser tries.
    """
    from django.contrib.auth import get_user_model

    from apps.exercises.services.generation_manifest import GenerationManifest

    User = get_user_model()

    # Auth check: require staff or superuser
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Permission denied."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"error": "Invalid JSON body."}, status=400
        )

    # Check if is_official=True but user is not superuser
    is_official = body.get("is_official", False)
    if is_official and not request.user.is_superuser:
        return JsonResponse(
            {"error": "Only superusers can create official exercises."},
            status=403
        )

    try:
        manifest = GenerationManifest(
            source=body.get("source", ""),
            source_ref=body.get("source_ref", ""),
            unit=body.get("unit", 0),
            skill_tags=body.get("skill_tags", []),
            exercise_types=body.get("exercise_types", []),
            key_set=body.get("key_set", []),
            playlist_target=body.get("playlist_target"),
            is_official=is_official,
            author_email=body.get("author_email", ""),
            dry_run=True,
        )
        summary = manifest.dry_run_summary()
        return JsonResponse(summary, status=200)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"Dry-run error: {e}")
        return JsonResponse(
            {"error": "Internal server error during dry-run."},
            status=500
        )


@require_POST
@login_required
def generation_manifest_execute_view(request):
    """POST /teacher/play/api/generate-manifest/execute/

    Accepts a JSON body matching GenerationManifest fields and executes the
    generation pipeline. Returns created exercise IDs or management command output.

    Request body (JSON):
      {
        "source": "bach_riemenschneider" | "played_in",
        "source_ref": "1-30" | "exercise_id",
        "unit": 9,
        "skill_tags": [],
        "exercise_types": ["play", "roman"],
        "key_set": ["C", "G"],
        "playlist_target": null,
        "is_official": false,
        "author_email": "teacher@example.com"
      }

    Response:
      {
        "created_count": 4,
        "exercise_ids": ["EA0001", "EA0002", "EA0003", "EA0004"]
      }

    For bach_riemenschneider source: created_count and exercise_ids may be empty
    (management commands don't easily return Exercise objects).

    Requires staff or superuser. Returns 403 if non-staff.
    is_official=True requires superuser. Returns 403 if non-superuser tries.
    """
    from django.contrib.auth import get_user_model

    from apps.exercises.services.generation_manifest import GenerationManifest

    User = get_user_model()

    # Auth check: require staff or superuser
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Permission denied."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"error": "Invalid JSON body."}, status=400
        )

    # Check if is_official=True but user is not superuser
    is_official = body.get("is_official", False)
    if is_official and not request.user.is_superuser:
        return JsonResponse(
            {"error": "Only superusers can create official exercises."},
            status=403
        )

    try:
        manifest = GenerationManifest(
            source=body.get("source", ""),
            source_ref=body.get("source_ref", ""),
            unit=body.get("unit", 0),
            skill_tags=body.get("skill_tags", []),
            exercise_types=body.get("exercise_types", []),
            key_set=body.get("key_set", []),
            playlist_target=body.get("playlist_target"),
            is_official=is_official,
            author_email=body.get("author_email", ""),
            dry_run=False,
        )
        created = manifest.execute()

        # Build response
        if isinstance(created, list):
            exercise_ids = [ex.id for ex in created]
            return JsonResponse(
                {
                    "created_count": len(exercise_ids),
                    "exercise_ids": exercise_ids,
                },
                status=200
            )
        else:
            # Bach generation returns empty list (or summary dict in dry-run)
            return JsonResponse(
                {
                    "created_count": 0,
                    "exercise_ids": [],
                },
                status=200
            )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return JsonResponse(
            {"error": "Internal server error during execution."},
            status=500
        )
