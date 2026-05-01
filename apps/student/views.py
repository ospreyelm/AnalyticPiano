import json
import uuid
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.student.unit_progress import get_unit_progress_data
from apps.student.unit1_curriculum import get_unit1_lane_groups
from apps.accounts.forms import CustomAuthenticationForm, RegistrationForm
from apps.exercises.models import (
    Exercise,
    IdentificationAttempt,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
    StudentSkillMastery,
)
from lab.views import RequirejsContext, generate_exercise_context
from apps.student.player_progression import (
    get_completed_exercise_ids,
    is_completed_identification_attempt,
    resolve_requested_step,
)

TAXONOMY_PATH = Path(__file__).resolve().parent.parent.parent / "music_theory_taxonomy_with_branches.json"


def _disable_computer_keyboard_input(exercise_context: dict, playlist: Playlist, exercise: Exercise) -> bool:
    playlist_tags = set((playlist.tags or []) + (playlist.skill_tags or []))
    exercise_tags = set(exercise.skill_tags or [])
    mode = exercise_context.get("mode")
    analysis_type = exercise_context.get("analysisType")
    return (
        "unit:1" in playlist_tags
        and "Note_Names" in (playlist_tags | exercise_tags)
        and mode == "playback"
        and analysis_type == "note_name"
    )


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


def _summarize_unit_progress(data: dict) -> dict:
    segments = data.get("bar_segments", [])
    mastered_count = sum(
        1 for segment in segments
        if segment["level"] == StudentSkillMastery.LEVEL_MASTERED
    )
    total = len(segments)
    percent = int(mastered_count / total * 100) if total else 0
    return {
        "percent": percent,
        "mastered_count": mastered_count,
        "resume_tag": None,
    }


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

class StudentLogoutView(View):
    def get(self, request):
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
        unit_meta = _load_unit_meta(1)
        unit1_data = get_unit_progress_data(request.user, "1")
        if unit1_data is None:
            raise Http404("Unit not found")
        unit1_progress = _summarize_unit_progress(unit1_data)
        resume_url, resume_label = _get_unit1_resume_target(request.user)

        units = [
            {
                "num": 1,
                "title": unit_meta.get("title", "Pitch & Staff Notation"),
                "feat": unit_meta.get("feat", ""),
                "percent": unit1_progress["percent"],
                "mastered_count": unit1_progress["mastered_count"],
                "total_skills": len(unit1_data.get("bar_segments", [])),
                "locked": False,
                "url": reverse("student:unit-progress", kwargs={"unit_n": "1"}),
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
            "resume_skill": resume_label,
            "unit1_progress": unit1_progress,
        })


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
        playlists_qs = Playlist.objects.filter(Q(is_public=True) | Q(authored_by=request.user)).order_by("name")
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
        for n_str in sorted(unit_groups.keys(), key=lambda k: int(k)):
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


def _student_player_url(unit_num: int, playlist: Playlist, exercise_num: int) -> str:
    return (
        reverse("student:player", kwargs={"unit_num": unit_num})
        + f"?playlist={playlist.id}&exercise_num={exercise_num}"
    )


def _build_student_player_payload(request, unit_num: int, playlist: Playlist, course, exercise_num: int):
    state = resolve_requested_step(request.user, playlist, exercise_num)
    if state.should_redirect:
        return redirect(_student_player_url(unit_num, playlist, state.exercise_num))

    resolved_num = state.exercise_num
    exercise = playlist.get_exercise_obj_by_num(resolved_num)
    if not exercise:
        return redirect(reverse("student:unit", kwargs={"unit_num": unit_num}))

    exercise_context = generate_exercise_context(
        resolved_num,
        exercise,
        request.user,
        playlist,
        course,
    )

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

    all_ids = list(playlist.untransposed_exercises_ids or [])
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
    else:
        prev_num = resolved_num - 1 if resolved_num > 1 else None
        next_num = resolved_num + 1 if resolved_num < playlist.exercise_count else None

    is_challenge = playlist.name and playlist.name.startswith(f"_challenge_{request.user.id}_")
    base_url = reverse("student:player", kwargs={"unit_num": unit_num}) + f"?playlist={playlist.id}"
    if is_challenge:
        base_url += "&mode=challenge"

    exercise_context["courseId"] = course.id if course else None
    exercise_context["playlistId"] = playlist.id
    exercise_context["totalExercises"] = playlist.exercise_count
    exercise_context["nextExercise"] = (
        f"{base_url}&exercise_num={next_num}" if next_num else None
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
    return exercise_context


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

        exercise_context = _build_student_player_payload(
            request, unit_num, playlist, course, exercise_num
        )
        if isinstance(exercise_context, HttpResponseRedirect):
            return exercise_context

        rj_context = RequirejsContext(settings.REQUIREJS_CONFIG, settings.REQUIREJS_DEBUG)
        rj_context.set_app_module("app/components/app/exercise")
        rj_context.set_module_params("app/components/app/exercise", exercise_context)

        context = {
            "unit_num": unit_num,
            "playlist": playlist,
            "exercise_num": exercise_context["exerciseNum"],
            "total_exercises": playlist.exercise_count,
            "is_review_mode": exercise_context["reviewMode"],
            "disable_computer_keyboard_input": exercise_context["disableComputerKeyboardInput"],
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
            return JsonResponse(
                {"redirect": reverse("student:unit", kwargs={"unit_num": unit_num})}
            )

        result = _build_student_player_payload(request, unit_num, playlist, course, exercise_num)
        if isinstance(result, HttpResponseRedirect):
            return JsonResponse({"redirect": result.url})
        return JsonResponse(result)


class ChallengeView(LoginRequiredMixin, View):
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


class UnitProgressView(LoginRequiredMixin, View):
    def get(self, request, unit_n):
        data = get_unit_progress_data(request.user, unit_n)
        if data is None:
            raise Http404("Unit not found")

        data["back_url"] = (
            reverse("student:home")
            if str(unit_n) == "1"
            else request.META.get("HTTP_REFERER") or reverse("student:home")
        )
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
