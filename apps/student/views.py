import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View

from apps.accounts.forms import CustomAuthenticationForm
from apps.exercises.models import Playlist
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


def _get_playlist_id_for_tag(tag: str) -> str | None:
    """Return the primary playlist ID for a Unit 1 skill tag."""
    playlist = (
        Playlist.objects.filter(tags__contains=[f"unit:1"])
        .filter(tags__contains=[tag])
        .order_by("name")
        .first()
    )
    return playlist.id if playlist else None


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
        resume_playlist_id = _get_playlist_id_for_tag(unit1_progress["resume_tag"]) if unit1_progress["resume_tag"] else None
        if resume_playlist_id:
            resume_url = reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={resume_playlist_id}"

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
            playlist_id = _get_playlist_id_for_tag(tag)
            playlist_url = None
            if playlist_id:
                playlist_url = reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={playlist_id}"

            skills.append({
                "tag": tag,
                "name": skill_display_names.get(tag, tag),
                "level": s["level"],
                "playlist_url": playlist_url,
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
        if "unit:1" not in playlist.tags:
             raise Http404("Playlist not part of Unit 1.")

        # Always start at exercise 1 for student resume flow if not specified
        # (Though resume flow usually points to a specific playlist, the playlist itself manages its own exercise sequence)
        exercise_num = 1
        exercise = playlist.get_exercise_obj_by_num(exercise_num)
        if not exercise:
            raise Http404("No exercises in this playlist.")

        exercise_context = generate_exercise_context(
            exercise_num,
            exercise,
            request.user,
            playlist,
            None, # No course for now
        )

        rj_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)
        rj_context.set_app_module("app/components/app/exercise")
        rj_context.set_module_params("app/components/app/exercise", exercise_context)
        
        context = {
            "unit_num": unit_num,
            "playlist": playlist,
        }
        rj_context.add_to_view(context)

        return render(request, "student/player.html", context)
