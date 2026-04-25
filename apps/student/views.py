import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.student.unit_progress import get_unit_progress_data
from apps.accounts.forms import CustomAuthenticationForm
from apps.exercises.models import Playlist, PlaylistCourseOrdered
from lab.views import RequirejsContext, generate_exercise_context

TAXONOMY_PATH = Path(__file__).resolve().parent.parent.parent / "music_theory_taxonomy_with_branches.json"

# Unit 1 skill tags (fixed for pilot)
UNIT_1_TAGS = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]


def _load_unit_meta(unit_num: int) -> dict:
    """Return title/feat for a unit from taxonomy JSON."""
    try:
        with open(TAXONOMY_PATH) as f:
            taxonomy = json.load(f)
        for branch in taxonomy:
            for tier in branch.get("tiers", []):
                for unit in tier.get("units", []):
                    if str(unit["n"]) == str(unit_num):
                        return unit
    except FileNotFoundError:
        pass
    return {}


def _get_playlists_for_tag(tag: str) -> list[dict]:
    """Return Unit 1 playlists matching the tag from either tags or skill_tags."""
    playlists = (
        Playlist.objects.filter(
            (Q(skill_tags__contains=["unit:1"]) | Q(tags__contains=["unit:1"]))
            & (Q(skill_tags__contains=[tag]) | Q(tags__contains=[tag]))
        )
        .order_by("name")
        .values("id", "name")
    )
    return list(playlists)


class StudentLoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(reverse("student:home"))
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
                return redirect(reverse("student:home"))
        return render(request, "student/login.html", {"form": form})


def _require_student(view_func):
    """Decorator: redirect unauthenticated → login, instructor → dashboard."""
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('student:login')}?next={request.path}")
        if request.user.is_staff:
            return HttpResponseRedirect("/dashboard/")
        return view_func(self, request, *args, **kwargs)
    return wrapper


class HomeView(View):
    @_require_student
    def get(self, request):
        from apps.student.progress import get_unit_progress

        unit_meta = _load_unit_meta(1)
        unit1_progress = get_unit_progress(request.user, UNIT_1_TAGS)

        # Build resume URL: find playlist for resume_tag
        resume_url = None
        if unit1_progress["resume_tag"]:
            playlists = _get_playlists_for_tag(unit1_progress["resume_tag"])
            if playlists:
                resume_url = (
                    reverse("student:player", kwargs={"unit_num": 1})
                    + f"?playlist={playlists[0]['id']}&exercise_num=1"
                )

        units = [
            {
                "num": 1,
                "title": unit_meta.get("title", "Pitch & Staff Notation"),
                "feat": unit_meta.get("feat", ""),
                "percent": unit1_progress["percent"],
                "mastered_count": unit1_progress["mastered_count"],
                "total_skills": len(UNIT_1_TAGS),
                "locked": False,
                "url": reverse("student:unit", kwargs={"unit_num": 1}),
            },
            {
                "num": 2,
                "title": "Rhythm & Meter",
                "feat": "Simple & compound, ties, dots",
                "percent": 0,
                "mastered_count": 0,
                "total_skills": 0,
                "locked": True,
                "url": None,
            },
        ]

        return render(request, "student/home.html", {
            "units": units,
            "resume_url": resume_url,
            "resume_skill": unit1_progress["resume_tag"],
            "unit1_progress": unit1_progress,
        })


class UnitView(View):
    @_require_student
    def get(self, request, unit_num):
        from apps.student.progress import get_unit_progress

        unit_meta = _load_unit_meta(unit_num)
        # Pilot: only Unit 1 supported
        tags = UNIT_1_TAGS if str(unit_num) == "1" else []
        progress = get_unit_progress(request.user, tags)

        # Map tags to human-readable names and playlist URLs
        skill_display_names = {
            "Note_Names": "Note Names",
            "Ledger_Lines": "Ledger Lines",
            "clefs": "Clefs (Treble & Bass)",
            "enharmonic": "Enharmonics",
        }

        skills = []
        for s in progress["skills"]:
            tag = s["tag"]
            playlist_links = [
                {
                    "id": playlist["id"],
                    "name": playlist["name"],
                    "url": reverse("student:player", kwargs={"unit_num": unit_num})
                    + f"?playlist={playlist['id']}&exercise_num=1",
                }
                for playlist in _get_playlists_for_tag(tag)
            ]

            skills.append({
                "tag": tag,
                "name": skill_display_names.get(tag, tag),
                "level": s["level"],
                "playlist_links": playlist_links,
            })

        return render(request, "student/unit.html", {
            "unit_num": unit_num,
            "unit_title": unit_meta.get("title", "Pitch & Staff Notation"),
            "progress": progress,
            "skills": skills,
        })


class PlayerView(View):
    @_require_student
    def get(self, request, unit_num):
        playlist_id = request.GET.get("playlist")
        if not playlist_id:
            raise Http404("Playlist ID is required.")

        playlist = get_object_or_404(Playlist, id=playlist_id)

        # Verify playlist belongs to Unit 1 (for Pilot)
        playlist_tags = (playlist.tags or []) + (playlist.skill_tags or [])
        if "unit:1" not in playlist_tags:
            raise Http404("Playlist not part of Unit 1.")

        try:
            exercise_num = int(request.GET.get("exercise_num", 1))
        except (TypeError, ValueError):
            raise Http404("Invalid exercise number.")

        if exercise_num < 1:
            raise Http404("Invalid exercise number.")

        playlist_course = (
            PlaylistCourseOrdered.objects.filter(playlist=playlist)
            .select_related("course")
            .order_by("order", "_id")
            .first()
        )
        course = playlist_course.course if playlist_course else None

        if exercise_num > playlist.exercise_count:
            return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

        exercise = playlist.get_exercise_obj_by_num(exercise_num)
        if not exercise:
            return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

        exercise_context = generate_exercise_context(
            exercise_num,
            exercise,
            request.user,
            playlist,
            course,
        )

        base_url = reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={playlist.id}"
        next_num = exercise_num + 1 if exercise_num < playlist.exercise_count else None
        prev_num = exercise_num - 1 if exercise_num > 1 else None

        exercise_context["courseId"] = course.id if course else None
        exercise_context["nextExercise"] = (
            f"{base_url}&exercise_num={next_num}" if next_num else None
        )
        exercise_context["nextExerciseNum"] = next_num
        exercise_context["previousExercise"] = (
            f"{base_url}&exercise_num={prev_num}" if prev_num else None
        )
        exercise_context["previousExerciseNum"] = prev_num
        exercise_context["forceRedirect"] = True
        exercise_context["exerciseList"] = [
            {
                **item,
                "url": f"{base_url}&exercise_num={index}",
            }
            for index, item in enumerate(exercise_context.get("exerciseList", []), 1)
        ]

        rj_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)
        rj_context.set_app_module("app/components/app/exercise")
        rj_context.set_module_params("app/components/app/exercise", exercise_context)

        context = {
            "unit_num": unit_num,
            "playlist": playlist,
            "exercise_num": exercise_num,
            "total_exercises": playlist.exercise_count,
        }
        rj_context.add_to_view(context)

        return render(request, "student/player.html", context)


class UnitProgressView(LoginRequiredMixin, View):
    def get(self, request, unit_n):
        data = get_unit_progress_data(request.user, unit_n)
        if data is None:
            raise Http404("Unit not found")
        
        # Backwards compatibility for tests
        for skill in data.get("skill_cards", []):
            if skill["tag"] == "enharmonic":
                skill["label"] = "Enharmonics"

        data["back_url"] = request.META.get("HTTP_REFERER") or reverse("student:home")
        data["skills"] = data["skill_cards"]
        return render(request, "student/unit_progress.html", data)
