import datetime
import json
import uuid
from collections import defaultdict
from functools import wraps
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.accounts.models import ROLE_TEACHER
from apps.accounts.navigation import home_url_for_user
from apps.student.unit_progress import (
    get_unit_progress_data,
    get_next_unit_playlist,
)
from apps.student.unit1_curriculum import get_unit1_lane_groups
from apps.exercises.taxonomy_reader import TaxonomyReader
from apps.student.access import accessible_playlist_queryset, user_can_access_playlist
from apps.accounts.forms import CustomAuthenticationForm, RegistrationForm
from apps.exercises.models import (
    Course,
    Exercise,
    IdentificationAttempt,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
)
from apps.exercises.services.exercise_context import (
    generate_exercise_context,
    get_adaptive_exercise_for_view,
)
from lab.views import RequirejsContext
from apps.student.player_progression import (
    PlayerProgressState,
    get_completed_exercise_ids,
    get_ordered_exercise_ids_for_serving,
    get_served_exercise_id,
    is_completed_identification_attempt,
    resolve_adaptive_step,
    resolve_requested_step,
)
from apps.student.home_context import (
    _batch_home_unit_summaries,
    _empty_unit_progress_summary,
    _summarize_unit_from_skill_levels,
    _summarize_unit_progress,
)
from apps.student.unit_metadata import (
    _load_unit_meta,
    _taxonomy_units_from_branches,
    _unit_date_labels,
    unit_sort_key,
)


def _disable_computer_keyboard_input(exercise_context: dict, playlist: Playlist, exercise: Exercise) -> bool:
    tags = set((playlist.tags or []) + (playlist.skill_tags or []) + (exercise_context.get("skillTags") or []))
    playlist_name = (playlist.name or "").lower()
    description = (exercise.description or "").lower()
    source = str(exercise_context.get("introText") or exercise_context.get("source") or "").lower()

    is_play_from_name_lane = (
        "play from name" in playlist_name
        or " note names (" in playlist_name and " play)" in playlist_name
        or "(exact)" in description
        or source.startswith("play the notes:")
    )

    return "unit:1" in tags and "Note_Names" in tags and is_play_from_name_lane


def _user_completed_exercise_ids(user, playlist: Playlist) -> set[str]:
    pd_rows = PerformanceData.objects.filter(user=user, playlist=playlist)
    ident_attempts = IdentificationAttempt.objects.filter(user=user, playlist=playlist)

    completed_ids = {
        entry["id"]
        for pd in pd_rows
        for entry in (pd.data or [])
        if "id" in entry
    }
    completed_ids.update(
        attempt.exercise.id
        for attempt in ident_attempts
        if attempt.exercise and is_completed_identification_attempt(attempt)
    )
    return completed_ids


def _get_unit1_resume_target(user) -> tuple[str, str]:
    try:
        lane_groups = get_unit1_lane_groups()
    except (ImproperlyConfigured, Playlist.DoesNotExist):
        return reverse("student:unit-progress", kwargs={"unit_n": "1"}), "Unit 1"

    for group in lane_groups:
        for lane in group.get("lanes", []):
            playlist = Playlist.objects.get(id=lane["playlist_id"])
            completed_ids = _user_completed_exercise_ids(user, playlist)
            for idx, exercise_id in enumerate(playlist.untransposed_exercises_ids, 1):
                if exercise_id not in completed_ids:
                    return (
                        reverse("student:player", kwargs={"unit_num": 1})
                        + f"?playlist={playlist.id}&exercise_num={idx}",
                        f"{group['title']} · {lane['label']}",
                    )

    return reverse("student:unit-progress", kwargs={"unit_n": "1"}), "Unit 1"


def _get_course_unit_dates(user) -> dict[str, dict]:
    """Map unit number → schedule info from the user's enrolled courses.

    Enrollment = membership in a Group that a Course is visible_to. Courses do
    not gate unit availability (factory playlists stay public); they only add
    publish/due dates for sequencing and grading.

    Returns {unit_n: {"due": datetime|None, "publish": datetime|None,
                      "published": bool, "course_title": str}} keeping the
    earliest due date when several playlists/courses tag the same unit.
    """
    from django.utils.timezone import now as tz_now

    rows = (
        PlaylistCourseOrdered.objects.filter(course__visible_to__members=user)
        .select_related("course", "playlist")
    )
    out: dict[str, dict] = {}
    current = tz_now()
    for pco in rows:
        tags = list(pco.playlist.skill_tags or []) + list(pco.playlist.tags or [])
        unit_numbers = {
            tag.split(":", 1)[1]
            for tag in tags
            if isinstance(tag, str) and tag.startswith("unit:")
        }
        for unit_n in unit_numbers:
            existing = out.get(unit_n)
            if existing is not None and existing["due"] is not None and (
                pco.due_date is None or pco.due_date >= existing["due"]
            ):
                continue
            out[unit_n] = {
                "due": pco.due_date,
                "publish": pco.publish_date,
                "published": pco.publish_date is None or pco.publish_date <= current,
                "course_title": pco.course.title,
            }
    return out


def resolve_course_for_playlist(user, playlist):
    """Pick the Course a performance should attribute to for this playlist.

    Prefer a course the user is enrolled in (group membership) over the bare
    first PlaylistCourseOrdered row — a playlist may sit in several courses.
    """
    base = (
        PlaylistCourseOrdered.objects.filter(playlist=playlist)
        .select_related("course")
        .order_by("order", "_id")
    )
    enrolled = base.filter(course__visible_to__members=user).first()
    if enrolled is not None:
        return enrolled.course
    fallback = base.first()
    return fallback.course if fallback else None


def _attach_harmonization_review(exercise_context, user, playlist, course, exercise):
    """Embed the student's best stored harmonization pass for review mode.

    No-op unless the exercise is a harmonization exercise and a pass exists.
    """
    if exercise_context.get("mode") != "harmonization":
        return
    pd = (
        PerformanceData.objects.filter(user=user, playlist=playlist, course=course)
        .first()
    )
    if not pd:
        return
    sonorities = pd.get_best_harmonization_pass(exercise.id)
    if sonorities:
        exercise_context["reviewHarmonizationSonorities"] = sonorities


def _get_available_unit_numbers(user) -> set[str]:
    available = set()
    playlists = accessible_playlist_queryset(user).order_by("name")

    for playlist in playlists:
        tags = list(playlist.skill_tags or []) + list(playlist.tags or [])

        for tag in tags:
            if isinstance(tag, str) and tag.startswith("unit:"):
                available.add(tag.split(":", 1)[1])
                continue

            unit = TaxonomyReader.get_unit_for_tag(tag)
            if unit:
                available.add(str(unit["n"]))

    return available


def _build_home_units(
    user,
    available_unit_numbers: set[str] | None = None,
    progress_by_unit: dict[str, dict] | None = None,
    units: list[dict] | None = None,
    course_dates: dict[str, dict] | None = None,
) -> list[dict]:
    if available_unit_numbers is None:
        available_unit_numbers = _get_available_unit_numbers(user)
    if units is None:
        units = TaxonomyReader.get_all_units()
    if progress_by_unit is None:
        progress_by_unit = _batch_home_unit_summaries(user, units, available_unit_numbers)
    if course_dates is None:
        course_dates = _get_course_unit_dates(user)

    home_units = []

    sorted_units = sorted(units, key=lambda item: unit_sort_key(str(item["n"])))
    for unit in sorted_units:
        unit_n = str(unit["n"])
        is_available = unit_n in available_unit_numbers
        progress = (
            progress_by_unit.get(unit_n, _empty_unit_progress_summary())
            if is_available
            else _empty_unit_progress_summary()
        )

        home_units.append(
            {
                "num": unit_n,
                "title": unit.get("title", f"Unit {unit_n}"),
                "feat": unit.get("feat", ""),
                "percent": progress["percent"],
                "mastered_count": progress["mastered_count"],
                "total_skills": len(unit.get("tags", [])),
                "locked": not is_available,
                "url": (
                    reverse("student:unit-progress", kwargs={"unit_n": unit_n})
                    if is_available
                    else None
                ),
                **_unit_date_labels(course_dates.get(unit_n)),
            }
        )

    return home_units


def _build_home_sections(
    user,
    available_unit_numbers: set[str] | None = None,
    progress_by_unit: dict[str, dict] | None = None,
    branches: list[dict] | None = None,
    course_dates: dict[str, dict] | None = None,
) -> list[dict]:
    """Build sections → tiers → units structure from taxonomy, preserving tier metadata.
    Splits standard sequence (core) tiers into individual top-level sections for balanced grid layout.
    """
    if branches is None:
        branches = TaxonomyReader.get_branches()
    if available_unit_numbers is None:
        available_unit_numbers = _get_available_unit_numbers(user)
    if progress_by_unit is None:
        progress_by_unit = _batch_home_unit_summaries(
            user,
            _taxonomy_units_from_branches(branches),
            available_unit_numbers,
        )
    if course_dates is None:
        course_dates = _get_course_unit_dates(user)

    # Track whether we've found the student's active tier yet (first tier
    # containing an unlocked unit with progress < 100%).
    found_active = False

    sections = []
    for branch in branches:
        branch_id = branch.get("id", "core")
        is_core = branch_id == "core"

        branch_tiers = branch.get("tiers", [])
        for tier_index, tier in enumerate(branch_tiers):
            tier_units = []
            started_count = 0
            mastered_count = 0

            sorted_units = sorted(
                tier.get("units", []),
                key=lambda u: unit_sort_key(str(u["n"])),
            )
            for unit in sorted_units:
                unit_n = str(unit["n"])
                is_available = unit_n in available_unit_numbers
                progress = (
                    progress_by_unit.get(unit_n, _empty_unit_progress_summary())
                    if is_available
                    else _empty_unit_progress_summary()
                )

                if is_available and progress["percent"] > 0:
                    started_count += 1
                if progress["percent"] >= 100:
                    mastered_count += 1

                tier_units.append({
                    "num": unit_n,
                    "title": unit.get("title", f"Unit {unit_n}"),
                    "feat": unit.get("feat", ""),
                    "percent": progress["percent"],
                    "mastered_count": progress["mastered_count"],
                    "total_skills": len(unit.get("tags", [])),
                    "locked": not is_available,
                    "url": (
                        reverse("student:unit-progress", kwargs={"unit_n": unit_n})
                        if is_available
                        else None
                    ),
                    **_unit_date_labels(course_dates.get(unit_n)),
                })

            # A tier is "active" if it's the first one we encounter that has an
            # unlocked unit with percent < 100 (i.e. the student should be here).
            has_active = False
            if not found_active:
                for u in tier_units:
                    if not u["locked"] and u["percent"] < 100:
                        has_active = True
                        found_active = True
                        break

            total_units = len(tier_units)
            tier_data = {
                "label": tier.get("label", ""),
                "badge": tier.get("badge", ""),
                "desc": tier.get("desc", ""),
                "units": tier_units,
                "has_active": has_active,
                "stats": {
                    "total": total_units,
                    "started": started_count,
                    "mastered": mastered_count,
                },
            }

            if is_core:
                # For Core, each tier becomes a separate top-level section/card
                sections.append({
                    "id": f"core_{tier_index}",
                    "label": tier.get("label", f"Standard {tier_index + 1}"),
                    "desc": tier.get("desc", ""),
                    "tiers": [tier_data],
                    "tier_count": 1,
                    "unit_count": total_units,
                    "has_active": has_active,
                })
            else:
                # For other branches, group tiers inside the branch section
                if tier_index == 0:
                    sections.append({
                        "id": branch_id,
                        "label": branch.get("label", branch_id),
                        "desc": branch.get("desc", ""),
                        "tiers": [],
                    })
                sections[-1]["tiers"].append(tier_data)

    # For non-core branches, compute section-level stats
    for section in sections:
        if not section["id"].startswith("core_"):
            section["tier_count"] = len(section["tiers"])
            section["unit_count"] = sum(t["stats"]["total"] for t in section["tiers"])
            section["has_active"] = any(t["has_active"] for t in section["tiers"])

    return sections


def _get_resume_target(
    user,
    available: set[str] | None = None,
    progress_by_unit: dict[str, dict] | None = None,
    branches: list[dict] | None = None,
) -> tuple[str | None, str | None, dict]:
    """Find the first incomplete unlocked unit across all branches/tiers.

    Returns (resume_url, resume_label, progress_summary).
    Falls back to Unit 1 if nothing else is found.
    """
    if branches is None:
        branches = TaxonomyReader.get_branches()
    if available is None:
        available = _get_available_unit_numbers(user)
    if progress_by_unit is None:
        progress_by_unit = _batch_home_unit_summaries(
            user,
            _taxonomy_units_from_branches(branches),
            available,
        )

    for branch in branches:
        for tier in branch.get("tiers", []):
            sorted_units = sorted(
                tier.get("units", []),
                key=lambda u: unit_sort_key(str(u["n"])),
            )
            for unit in sorted_units:
                unit_n = str(unit["n"])
                if unit_n not in available:
                    continue
                progress = progress_by_unit.get(unit_n, _empty_unit_progress_summary())
                if progress["percent"] < 100:
                    # For Unit 1 use the lane-level resume logic
                    if unit_n == "1":
                        url, label = _get_unit1_resume_target(user)
                        return url, label, progress
                    url = reverse(
                        "student:unit-progress", kwargs={"unit_n": unit_n}
                    )
                    label = f"Unit {unit_n} · {unit.get('title', '')}"
                    return url, label, progress

    # Fallback: Unit 1
    progress = progress_by_unit.get("1")
    if progress is None:
        unit1_data = get_unit_progress_data(user, "1")
        progress = (
            _summarize_unit_progress(unit1_data)
            if unit1_data
            else _empty_unit_progress_summary()
        )
    url = reverse("student:unit-progress", kwargs={"unit_n": "1"})
    return url, "Unit 1 · Pitch & staff notation", progress


def _get_enrolled_courses_with_pcos(user) -> tuple[list, dict]:
    """Return (courses_list, pcos_by_course_id) using a single PCO query.

    courses_list — distinct Course objects the user is enrolled in, ordered by title.
    pcos_by_course_id — defaultdict(list) mapping course.pk → list of PCO objects.
    """
    all_pcos = list(
        PlaylistCourseOrdered.objects
        .filter(course__visible_to__members=user)
        .select_related("course", "playlist")
        .distinct()
    )
    pcos_by_course_id: dict = defaultdict(list)
    courses_map: dict = {}
    for pco in all_pcos:
        pcos_by_course_id[pco.course.pk].append(pco)
        if pco.course.pk not in courses_map:
            courses_map[pco.course.pk] = pco.course

    courses_list = sorted(courses_map.values(), key=lambda c: c.title)
    return courses_list, pcos_by_course_id


def _build_course_panels(
    user,
    courses_and_pcos=None,
) -> list[dict]:
    """Return one dict per enrolled course for the student home page."""

    from apps.student.unit_progress import _batch_playlist_data, _playlist_stats
    from django.utils.timezone import now as tz_now

    _FAR_FUTURE = datetime.datetime(2999, 12, 31, tzinfo=datetime.timezone.utc)

    if courses_and_pcos is not None:
        courses, pcos_by_course = courses_and_pcos
    else:
        courses, pcos_by_course = _get_enrolled_courses_with_pcos(user)

    all_playlists = [
        pco.playlist
        for pco_rows in pcos_by_course.values()
        for pco in pco_rows
    ]
    raw_by_pk = _batch_playlist_data(user, all_playlists) if all_playlists else {}
    current = tz_now()

    panels = []
    for course in courses:
        pco_rows = pcos_by_course[course.pk]

        pct_sum = 0
        open_count = 0
        due_count = 0
        overdue_count = 0
        next_candidates = []  # (pco, stats) for published, incomplete PCOs

        for pco in pco_rows:
            pl = pco.playlist
            stats = (
                _playlist_stats(pl, raw_by_pk[pl.pk])
                if pl.pk in raw_by_pk
                else {"done": 0, "total": 0, "url": None}
            )
            pco_pct = min(100, stats["done"] * 100 // stats["total"]) if stats["total"] else 0
            pct_sum += pco_pct

            is_upcoming = pco.publish_date is not None and pco.publish_date > current
            is_complete = pco_pct >= 100
            if not is_upcoming and not is_complete:
                open_count += 1
                if stats.get("total", 0) > 0:
                    next_candidates.append((pco, stats))
                if pco.due_date is not None:
                    due_count += 1
                    if pco.due_date < current:
                        overdue_count += 1

        # Pick "next up": earliest due date (nulls last), then playlist order.
        next_candidates.sort(
            key=lambda t: (
                t[0].due_date is None,
                t[0].due_date if t[0].due_date is not None else _FAR_FUTURE,
                t[0].order,
            )
        )

        next_url = None
        next_name = None
        next_due_label = None
        if next_candidates:
            winner_pco, winner_stats = next_candidates[0]
            next_url = winner_stats["url"]  # always non-None when total > 0 (guarded above)
            next_name = winner_pco.playlist.name
            date_labels = _unit_date_labels({
                "due": winner_pco.due_date,
                "publish": None,
                "published": True,
            })
            next_due_label = date_labels["due_label"]

        avg_pct = int(pct_sum / len(pco_rows)) if pco_rows else 0
        panels.append({
            "title": course.title,
            "progress_pct": avg_pct,
            "course_pk": course.pk,
            "open_count": open_count,
            "due_count": due_count,
            "overdue_count": overdue_count,
            "next_url": next_url,
            "next_name": next_name,
            "next_due_label": next_due_label,
        })

    return panels


def _build_home_context(user) -> dict:
    branches = TaxonomyReader.get_branches()
    units = _taxonomy_units_from_branches(branches)
    available = _get_available_unit_numbers(user)
    progress_by_unit = _batch_home_unit_summaries(user, units, available)
    course_dates = _get_course_unit_dates(user)
    courses_and_pcos = _get_enrolled_courses_with_pcos(user)
    course_panels = _build_course_panels(
        user,
        courses_and_pcos=courses_and_pcos,
    )
    resume_url, resume_label, resume_progress = _get_resume_target(
        user,
        available=available,
        progress_by_unit=progress_by_unit,
        branches=branches,
    )
    return {
        "sections": _build_home_sections(
            user,
            available_unit_numbers=available,
            progress_by_unit=progress_by_unit,
            branches=branches,
            course_dates=course_dates,
        ),
        "units": _build_home_units(
            user,
            available_unit_numbers=available,
            progress_by_unit=progress_by_unit,
            units=units,
            course_dates=course_dates,
        ),
        "resume_url": resume_url,
        "resume_skill": resume_label,
        "resume_progress": resume_progress,
        "course_panels": course_panels,
    }


class StudentLoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(home_url_for_user(request.user))
        form = CustomAuthenticationForm()
        return render(request, "student/login.html", {"form": form})

    def post(self, request):
        form = CustomAuthenticationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user = authenticate(username=email, password=password)
            if user is not None:
                django_login(request, user)
                if user.is_superuser or user.role == ROLE_TEACHER:
                    return redirect(home_url_for_user(user))
                next_url = request.GET.get("next")
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect(home_url_for_user(user))
        return render(request, "student/login.html", {"form": form})

class StudentLogoutView(View):
    http_method_names = ["post"]

    def post(self, request):
        django_logout(request)
        return redirect(reverse("student:login"))

class StudentSignupView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(reverse("student:home"))
        form = RegistrationForm()
        return render(request, "student/signup.html", {"form": form})

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.backend = "django.contrib.auth.backends.ModelBackend"
            django_login(request, user)
            return redirect(reverse("student:home"))
        return render(request, "student/signup.html", {"form": form})


def _require_student(view_func):
    """Decorator: redirect unauthenticated users to login and teachers home."""
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('student:login')}?next={request.path}")
        if request.user.is_superuser or request.user.role == ROLE_TEACHER:
            return redirect(home_url_for_user(request.user))
        return view_func(self, request, *args, **kwargs)
    return wrapper


class StudentRoleRequiredMixin(LoginRequiredMixin):
    login_url = reverse_lazy("student:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and (
            request.user.is_superuser or request.user.role == ROLE_TEACHER
        ):
            return redirect(home_url_for_user(request.user))
        return super().dispatch(request, *args, **kwargs)


class CourseDetailView(View):
    @_require_student
    def get(self, request, pk):
        from apps.student.unit_progress import _batch_playlist_data, _playlist_stats
        from django.utils.timezone import now as tz_now, localtime

        course = Course.objects.filter(
            pk=pk, visible_to__members=request.user
        ).select_related("authored_by").distinct().first()
        if course is None:
            raise Http404("Course not found or not enrolled.")

        author = course.authored_by
        full_name = author.get_full_name()
        teacher_name = author.email if full_name == "[anonymous]" else full_name

        pcos = list(
            PlaylistCourseOrdered.objects
            .filter(course=course)
            .select_related("playlist")
            .order_by("order", "pk")
        )
        playlists = [pco.playlist for pco in pcos]
        raw_by_pk = _batch_playlist_data(request.user, playlists) if playlists else {}

        current = tz_now()
        open_assignments = []
        upcoming_assignments = []
        completed_assignments = []

        for pco in pcos:
            pl = pco.playlist
            stats = _playlist_stats(pl, raw_by_pk[pl.pk]) if pl.pk in raw_by_pk else {"done": 0, "total": 0, "url": None}
            progress_pct = min(100, stats["done"] * 100 // stats["total"]) if stats["total"] else 0

            if pco.publish_date is not None and pco.publish_date > current:
                status = "upcoming"
            elif progress_pct >= 100:
                status = "completed"
            else:
                status = "open"

            overdue = (
                status == "open"
                and pco.due_date is not None
                and pco.due_date < current
            )

            due_label = None
            opens_label = None
            if status == "upcoming" and pco.publish_date:
                opens_label = localtime(pco.publish_date).strftime("Opens %a %b %-d")
            elif pco.due_date is not None:
                due_label = localtime(pco.due_date).strftime("Due %a %b %-d")

            unit_tags = [
                t for t in list(pl.skill_tags or []) + list(pl.tags or [])
                if isinstance(t, str) and t.startswith("unit:")
            ]
            unit_n = unit_tags[0].split(":", 1)[1] if unit_tags else None

            if status == "upcoming":
                play_url = None
            elif status == "completed":
                play_url = (
                    reverse("student:player", kwargs={"unit_num": unit_n})
                    + f"?playlist={pl.id}&exercise_num=1"
                ) if unit_n else None
            else:  # open
                play_url = stats.get("url")

            row = {
                "playlist_id": pl.id,
                "name": pl.name,
                "order": pco.order,
                "status": status,
                "overdue": overdue,
                "progress_pct": progress_pct,
                "due_label": due_label,
                "opens_label": opens_label,
                "play_url": play_url,
            }

            if status == "open":
                open_assignments.append(row)
            elif status == "upcoming":
                upcoming_assignments.append(row)
            else:
                completed_assignments.append(row)

        all_pcts = [
            r["progress_pct"]
            for r in open_assignments + upcoming_assignments + completed_assignments
        ]
        overall_pct = int(sum(all_pcts) / len(all_pcts)) if all_pcts else 0

        return render(request, "student/course_detail.html", {
            "course": course,
            "teacher_name": teacher_name,
            "overall_pct": overall_pct,
            "open_assignments": open_assignments,
            "upcoming_assignments": upcoming_assignments,
            "completed_assignments": completed_assignments,
        })


class HomeView(View):
    @_require_student
    def get(self, request):
        context = _build_home_context(request.user)
        context['joined_course'] = request.session.pop('joined_course', None)
        context['next_assignment_url'] = request.session.pop('next_assignment_url', None)
        context['next_assignment_name'] = request.session.pop('next_assignment_name', None)
        return render(request, "student/home.html", context)


class JoinCourseView(View):
    """Student-styled enrollment: enter (or deep-link) a group join code."""

    @_require_student
    def get(self, request):
        prefill = request.GET.get("code", "").strip().upper()
        return render(request, "student/join.html", {"join_code": prefill, "error": None})

    @_require_student
    def post(self, request):
        from apps.accounts.models import Group

        code = request.POST.get("join_code", "").strip().upper()
        if not code:
            return render(
                request, "student/join.html",
                {"join_code": "", "error": "Please enter a join code."},
            )
        group = Group.objects.filter(join_code=code).first()
        if group is None:
            return render(
                request, "student/join.html",
                {"join_code": code,
                 "error": f'No class found with code "{code}". Check the code and try again.'},
            )
        if request.user == group.manager:
            return render(
                request, "student/join.html",
                {"join_code": code,
                 "error": "You are the teacher of this class — you cannot join it as a student."},
            )
        if not group.members.filter(pk=request.user.pk).exists():
            group.members.add(request.user)
        request.session['joined_course'] = group.name

        # Find first open published assignment for the "start here" link.
        from django.db.models import F as _F
        from django.utils.timezone import now as _tz_now
        from apps.student.unit_progress import _playlist_stats_by_id
        _now = _tz_now()
        _candidate_pcos = (
            PlaylistCourseOrdered.objects
            .filter(course__visible_to=group)
            .select_related("playlist")
            .order_by(_F("due_date").asc(nulls_last=True), "order")
        )
        for _pco in _candidate_pcos:
            if _pco.publish_date is not None and _pco.publish_date > _now:
                continue
            _pl = _pco.playlist
            _pl_tags = list(_pl.skill_tags or []) + list(_pl.tags or [])
            if not any(isinstance(t, str) and t.startswith("unit:") for t in _pl_tags):
                continue
            _stats = _playlist_stats_by_id(request.user, _pl.id)
            if _stats["total"] == 0 or _stats["done"] >= _stats["total"]:
                continue
            request.session["next_assignment_url"] = _stats["url"]
            request.session["next_assignment_name"] = _pl.name or ""
            break

        return redirect(reverse("student:home"))


class UnitView(View):
    @_require_student
    def get(self, request, unit_num):
        from apps.exercises.taxonomy_reader import TaxonomyReader

        if str(unit_num) == "1":
            return redirect(reverse("student:unit-progress", kwargs={"unit_n": "1"}))

        unit_meta = _load_unit_meta(unit_num)
        unit_data = get_unit_progress_data(request.user, str(unit_num))
        if unit_data is None:
            raise Http404("Unit not found")
        progress = _summarize_unit_progress(unit_data)
        skills = unit_data.get("skill_cards", [])

        # Group playlists by unit
        playlists_qs = accessible_playlist_queryset(request.user).order_by("name")
        unit_groups = {}
        ungrouped_playlists = []

        for pl in playlists_qs:
            pl_unit = None
            pl_skill_tags = pl.skill_tags or []
            for t in pl_skill_tags:
                pl_unit = TaxonomyReader.get_unit_for_tag(t)
                if pl_unit:
                    break
            
            pl_data = {
                "id": pl.id,
                "name": pl.name or pl.id,
                "url": reverse("student:player", kwargs={"unit_num": unit_num})
                + f"?playlist={pl.id}&exercise_num=1",
            }

            if pl_unit:
                n = str(pl_unit["n"])
                if n not in unit_groups:
                    unit_groups[n] = {
                        "unit": pl_unit,
                        "playlists": []
                    }
                unit_groups[n]["playlists"].append(pl_data)
            else:
                ungrouped_playlists.append(pl_data)

        sorted_groups = []
        for n_str in sorted(unit_groups.keys(), key=unit_sort_key):
            sorted_groups.append(unit_groups[n_str])
            
        if ungrouped_playlists:
            sorted_groups.append({
                "unit": None,
                "playlists": ungrouped_playlists
            })

        return render(request, "student/unit.html", {
            "unit_num": unit_num,
            "unit_title": unit_meta.get("title", "Pitch & Staff Notation"),
            "progress": progress,
            "skills": skills,
            "grouped_playlists": sorted_groups,
        })


class PlayerView(View):
    @_require_student
    def get(self, request, unit_num):
        playlist_id = request.GET.get("playlist")
        if not playlist_id:
            raise Http404("Playlist ID is required.")

        playlist = get_object_or_404(Playlist, id=playlist_id)
        if not user_can_access_playlist(request.user, playlist):
            raise Http404("Playlist not found.")

        # Verify playlist belongs to the requested unit.
        playlist_tags = (playlist.tags or []) + (playlist.skill_tags or [])
        unit_tag = f"unit:{unit_num}"
        if unit_tag not in playlist_tags:
            raise Http404(f"Playlist not part of Unit {unit_num}.")

        try:
            exercise_num = int(request.GET.get("exercise_num", 1))
        except (TypeError, ValueError):
            raise Http404("Invalid exercise number.")

        if exercise_num < 1:
            raise Http404("Invalid exercise number.")

        course = resolve_course_for_playlist(request.user, playlist)

        is_dynamic_or_adaptive = bool(playlist.is_dynamic or playlist.is_adaptive)
        served_ids = get_ordered_exercise_ids_for_serving(request.user, playlist)
        served_count = len(served_ids)

        if not is_dynamic_or_adaptive and exercise_num > served_count:
            return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

        if is_dynamic_or_adaptive:
            # Decouple exercise_num from the URL: the backend derives the slot
            # strictly from DB history (next pending slot) and redirects the
            # URL to match. See resolve_adaptive_step.
            state = resolve_adaptive_step(request.user, playlist, exercise_num, course)
        else:
            state = resolve_requested_step(request.user, playlist, exercise_num)

        if state.should_redirect:
            return redirect(
                reverse("student:player", kwargs={"unit_num": unit_num})
                + f"?playlist={playlist.id}&exercise_num={state.exercise_num}"
            )

        resolved_num = state.exercise_num
        exercise_num = resolved_num
        if is_dynamic_or_adaptive:
            exercise = get_adaptive_exercise_for_view(
                request,
                playlist,
                exercise_num,
                course.id if course else None,
            )
        else:
            exercise_id = get_served_exercise_id(request.user, playlist, exercise_num)
            exercise = Exercise.objects.filter(id=exercise_id).first() if exercise_id else None

        if not exercise:
            return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

        exercise_context = generate_exercise_context(
            exercise_num,
            exercise,
            request.user,
            playlist,
            course,
        )

        exercise_context["playlistId"] = playlist.id
        exercise_context["totalExercises"] = served_count
        exercise_context["reviewMode"] = state.mode == "review"
        exercise_context["playerMode"] = state.mode
        if state.mode == "review":
            attempts = (
                IdentificationAttempt.objects.filter(
                    user=request.user,
                    exercise=exercise,
                    playlist=playlist,
                )
                .order_by("submitted_at")
            )
            merged_answers = {}
            for attempt in attempts:
                if not is_completed_identification_attempt(attempt):
                    continue
                if attempt.answers:
                    merged_answers.update(attempt.answers)

            if merged_answers:
                exercise_context["reviewAnswers"] = merged_answers

            _attach_harmonization_review(
                exercise_context, request.user, playlist, course, exercise
            )

        all_ids = served_ids
        completed_ids = get_completed_exercise_ids(request.user, playlist)
        completed_nums = [
            index for index, exercise_id in enumerate(all_ids, 1)
            if exercise_id in completed_ids
        ]

        if state.mode == "review":
            earlier_completed = [n for n in completed_nums if n < resolved_num]
            later_completed = [n for n in completed_nums if n > resolved_num]
            prev_num = earlier_completed[-1] if earlier_completed else None

            next_pending = next((i for i, x in enumerate(all_ids, 1) if x not in completed_ids), None)
            if later_completed:
                next_num = later_completed[0]
            elif next_pending == resolved_num + 1:
                next_num = next_pending
            else:
                next_num = None
        elif is_dynamic_or_adaptive:
            prev_num = resolved_num - 1 if resolved_num > 1 else None
            next_num = resolved_num + 1
        else:
            prev_num = resolved_num - 1 if resolved_num > 1 else None
            next_num = resolved_num + 1 if resolved_num < playlist.exercise_count else None

        is_challenge = playlist.name and playlist.name.startswith(f"_challenge_{request.user.id}_")
        base_url = reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={playlist.id}"
        if is_challenge:
            base_url += "&mode=challenge"

        # When last exercise in playlist, link to first exercise of next unit playlist.
        next_playlist_first_url = None
        if not next_num and not is_challenge:
            next_pl = get_next_unit_playlist(request.user, unit_num, playlist)
            if next_pl:
                next_pl_base = reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={next_pl.id}"
                next_playlist_first_url = f"{next_pl_base}&exercise_num=1"

        exercise_context["courseId"] = course.id if course else None
        exercise_context["nextExercise"] = (
            f"{base_url}&exercise_num={next_num}" if next_num else next_playlist_first_url
        )
        exercise_context["nextExerciseNum"] = next_num
        exercise_context["nextExerciseId"] = (
            all_ids[next_num - 1] if next_num and next_num <= len(all_ids) else False
        )
        exercise_context["previousExercise"] = (
            f"{base_url}&exercise_num={prev_num}" if prev_num else None
        )
        exercise_context["previousExerciseNum"] = prev_num
        exercise_context["previousExerciseId"] = (
            all_ids[prev_num - 1] if prev_num and prev_num <= len(all_ids) else False
        )
        exercise_context["exerciseList"] = [
            {
                **item,
                "url": f"{base_url}&exercise_num={index}",
            }
            for index, item in enumerate(exercise_context.get("exerciseList", []), 1)
        ]
        exercise_context["disableComputerKeyboardInput"] = _disable_computer_keyboard_input(
            exercise_context, playlist, exercise
        )
        debug_exercise_db_json = None
        if settings.DEBUG and request.GET.get("debug_exercise") == "1":
            debug_exercise_db_json = json.dumps(
                {
                    "playlist": {
                        "id": playlist.id,
                        "name": playlist.name,
                        "skill_tags": playlist.skill_tags,
                    },
                    "servedExerciseNum": exercise_num,
                    "exercise": {
                        "id": exercise.id,
                        "description": exercise.description,
                        "skill_tags": exercise.skill_tags,
                        "complexity": exercise.complexity,
                        "data": exercise.data,
                    },
                    "frontendPayload": exercise_context,
                }
            )

        if exercise_context.get("type") in {"umto_symbolic_meter", "umto_barline_placement"}:
            context = {
                "unit_num": unit_num,
                "playlist": playlist,
                "playlist_name": playlist.name or playlist.id,
                "exercise_num": exercise_num,
                "total_exercises": served_count if served_count > 0 else exercise_num,
                "is_review_mode": state.mode == "review",
                "is_harmonization_review": (
                    state.mode == "review"
                    and exercise_context.get("mode") == "harmonization"
                ),
                "disable_computer_keyboard_input": exercise_context["disableComputerKeyboardInput"],
                "exercise_config_json": json.dumps(exercise_context),
                "debug_exercise_db_json": debug_exercise_db_json,
            }
            return render(request, "qa_player.html", context)

        rj_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)
        rj_context.set_app_module("app/components/app/exercise")
        rj_context.set_module_params("app/components/app/exercise", exercise_context)

        import re as _re
        _raw_name = playlist.name or ""
        _playlist_display_name = _re.sub(
            r"^Unit\s+" + str(unit_num) + r"\s*[·\-–—·]*\s*",
            "",
            _raw_name,
        ).strip() or _raw_name

        context = {
            "unit_num": unit_num,
            "playlist": playlist,
            "playlist_display_name": _playlist_display_name,
            "exercise_num": exercise_num,
            "total_exercises": served_count if served_count > 0 else exercise_num,
            "is_review_mode": state.mode == "review",
            "is_harmonization_review": (
                state.mode == "review"
                and exercise_context.get("mode") == "harmonization"
            ),
            "disable_computer_keyboard_input": exercise_context["disableComputerKeyboardInput"],
            "debug_exercise_db_json": debug_exercise_db_json,
        }
        rj_context.add_to_view(context)

        return render(request, "student/player.html", context)


class PlayerDefinitionView(View):
    @_require_student
    def get(self, request, unit_num):
        playlist_id = request.GET.get("playlist")
        if not playlist_id:
            raise Http404("Playlist ID is required.")

        playlist = get_object_or_404(Playlist, id=playlist_id)

        playlist_tags = (playlist.tags or []) + (playlist.skill_tags or [])
        unit_tag = f"unit:{unit_num}"
        if unit_tag not in playlist_tags:
            raise Http404(f"Playlist not part of Unit {unit_num}.")

        try:
            exercise_num = int(request.GET.get("exercise_num", 1))
        except (TypeError, ValueError):
            raise Http404("Invalid exercise number.")

        if exercise_num < 1:
            raise Http404("Invalid exercise number.")

        course = resolve_course_for_playlist(request.user, playlist)

        is_dynamic_or_adaptive = bool(playlist.is_dynamic or playlist.is_adaptive)
        served_count = len(get_ordered_exercise_ids_for_serving(request.user, playlist))
        if not is_dynamic_or_adaptive and exercise_num > served_count:
            return JsonResponse(
                {"redirect": reverse("student:unit", kwargs={"unit_num": unit_num})}
            )

        if is_dynamic_or_adaptive:
            # Decouple exercise_num from the URL for adaptive/dynamic playlists;
            # the backend derives the slot from DB history (resolve_adaptive_step)
            # and generates/reserves via the adaptive engine, not the ordered-ids
            # path used by static playlists.
            state = resolve_adaptive_step(request.user, playlist, exercise_num, course)
        else:
            state = resolve_requested_step(request.user, playlist, exercise_num)
        # When the URL's exercise_num doesn't match the DB-derived slot, serve the
        # derived-slot exercise in place and expose the pinned URL so the client
        # can history.replaceState. Returning a hard {redirect} here would make
        # the client set window.location.href, turning every SPA advance (the
        # auto-advance after the score card) into a full page reload.
        pinned_url = (
            reverse("student:player", kwargs={"unit_num": unit_num})
            + f"?playlist={playlist.id}&exercise_num={state.exercise_num}"
        )

        if is_dynamic_or_adaptive:
            exercise = get_adaptive_exercise_for_view(
                request, playlist, state.exercise_num, course.id if course else None
            )
        else:
            exercise_id = get_served_exercise_id(request.user, playlist, state.exercise_num)
            exercise = Exercise.objects.filter(id=exercise_id).first() if exercise_id else None
        if not exercise:
            return JsonResponse(
                {"redirect": reverse("student:unit", kwargs={"unit_num": unit_num})}
            )

        exercise_context = generate_exercise_context(
            state.exercise_num, exercise, request.user, playlist, course
        )
        exercise_context["playlistId"] = playlist.id
        exercise_context["totalExercises"] = served_count
        exercise_context["reviewMode"] = state.mode == "review"
        exercise_context["pinnedUrl"] = pinned_url
        if state.mode == "review":
            attempts = (
                IdentificationAttempt.objects.filter(
                    user=request.user,
                    exercise=exercise,
                    playlist=playlist,
                )
                .order_by("submitted_at")
            )
            merged_answers = {}
            for attempt in attempts:
                if not is_completed_identification_attempt(attempt):
                    continue
                if attempt.answers:
                    merged_answers.update(attempt.answers)

            if merged_answers:
                exercise_context["reviewAnswers"] = merged_answers

            _attach_harmonization_review(
                exercise_context, request.user, playlist, course, exercise
            )

        return JsonResponse(exercise_context)


class ChallengeView(StudentRoleRequiredMixin, View):
    def get(self, request, group_key):
        from apps.student.unit1_curriculum import get_unit1_challenge_source_exercises, CHALLENGE_GROUPS
        from apps.student.unit_progress import get_unit_progress_data
        from apps.exercises.models import Playlist, ExercisePlaylistOrdered
        
        if group_key not in ["treble", "bass"]:
            raise Http404("Invalid challenge group.")
            
        unit1_data = get_unit_progress_data(request.user, "1")
        lane_masteries = {seg["tag"]: seg["level"] for seg in unit1_data.get("bar_segments", [])}
        
        group = CHALLENGE_GROUPS[group_key]
        is_unlocked = True
        for tag in group["lane_keys"]:
            if lane_masteries.get(tag, "not_started") not in ["proficient", "mastered"]:
                is_unlocked = False
                break
                
        if not is_unlocked:
            return redirect(reverse("student:unit-progress", kwargs={"unit_n": "1"}))
            
        source_exs = get_unit1_challenge_source_exercises(group_key)
        lane_exercises = {}
        for lane_key in group["lane_keys"]:
            exs = source_exs.get(lane_key, [])
            if len(exs) < 2:
                raise Http404(f"Lane {lane_key} lacks sufficient challenge-eligible items (needs 2, found {len(exs)}).")
            lane_exercises[lane_key] = exs[:2]
            
        interleaved_exercises = []
        for i in range(2):
            for lane_key in group["lane_keys"]:
                interleaved_exercises.append(lane_exercises[lane_key][i])
                
        playlist_name = f"_challenge_{request.user.id}_{group_key}_{uuid.uuid4().hex[:8]}"

        playlist = Playlist.objects.create(
            name=playlist_name,
            authored_by=request.user,
            is_public=False,
            skill_tags=["unit:1"]
        )
        
        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        
        for idx, ex in enumerate(interleaved_exercises):
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist,
                exercise=ex,
                order=idx + 1,
                difficulty_tier=3,
                is_mastery_challenge_source=True
            )
            
        player_url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={playlist.id}&exercise_num=1&mode=challenge"
        return redirect(player_url)


class UnitProgressView(StudentRoleRequiredMixin, View):
    def get(self, request, unit_n):
        data = get_unit_progress_data(request.user, unit_n)
        if data is None:
            raise Http404("Unit not found")

        data["back_url"] = reverse("student:home")
        data["skills"] = data["skill_cards"]
        
        if str(unit_n) == "1":
            lane_masteries = {seg["tag"]: seg["level"] for seg in data.get("bar_segments", [])}
            
            treble_proficient = True
            for tag in ["identify_treble", "play_from_name_treble", "play_the_notes_treble"]:
                if lane_masteries.get(tag, "not_started") not in ["proficient", "mastered"]:
                    treble_proficient = False
                    break
                    
            bass_proficient = True
            for tag in ["identify_bass", "play_from_name_bass", "play_the_notes_bass"]:
                if lane_masteries.get(tag, "not_started") not in ["proficient", "mastered"]:
                    bass_proficient = False
                    break
                    
            from apps.student.unit_progress import _check_challenge_mastery
            treble_mastered = _check_challenge_mastery(request.user, "treble")
            bass_mastered = _check_challenge_mastery(request.user, "bass")
            
            data["challenges"] = {
                "treble": {
                    "unlocked": treble_proficient,
                    "mastered": treble_mastered,
                    "url": reverse("student:unit1-challenge", kwargs={"group_key": "treble"}) if treble_proficient else "#",
                },
                "bass": {
                    "unlocked": bass_proficient,
                    "mastered": bass_mastered,
                    "url": reverse("student:unit1-challenge", kwargs={"group_key": "bass"}) if bass_proficient else "#",
                }
            }
            
        return render(request, "student/unit_progress.html", data)
