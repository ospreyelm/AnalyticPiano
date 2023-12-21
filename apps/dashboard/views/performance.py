from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe
from django_tables2 import RequestConfig, Column
from datetime import datetime
import pytz

from apps.dashboard.tables import MyActivityTable, MyActivityDetailsTable
from apps.exercises.models import Course, PerformanceData, Playlist
from django.conf import settings

User = get_user_model()


@login_required
def performance_list_view(request, subscriber_id=None):
    subscriber_id = subscriber_id or request.user.id
    subscriber = get_object_or_404(User, id=subscriber_id)

    if (
        request.user != subscriber
        and not request.user.pk in subscriber.performance_permits
    ):
        raise PermissionDenied

    performances = PerformanceData.objects.filter(user=subscriber).select_related(
        "user", "playlist", "course"
    )

    table = MyActivityTable(performances)
    performer_name = subscriber

    RequestConfig(request).configure(table)
    return render(
        request,
        "dashboard/performances-list.html",
        {"table": table, "performer_name": performer_name, "me": request.user},
    )


def playlist_pass_bool(exercise_list, exercises_data, playlist_length):
    parsed_data = {}

    for completion in exercises_data:
        c_id = completion["id"]
        if c_id not in parsed_data.keys():
            parsed_data[c_id] = []
        parsed_data[c_id].append(completion["error_tally"])
        del c_id

    playlist_pass = True
    if len(parsed_data.keys()) < playlist_length:
        playlist_pass = False
    else:
        for item in exercise_list:
            if item not in parsed_data.keys():
                playlist_pass = False
                break
        for key in parsed_data:
            least_err = sorted(parsed_data[key])[0]
            if isinstance(least_err, int) and least_err > 0:
                playlist_pass = False
                break
    return playlist_pass


def playlist_pass_date(
    exercise_list, exercises_data, playlist_length, make_concise_and_localize=True
):
    if not playlist_pass_bool(exercise_list, exercises_data, playlist_length):
        return None

    parsed_data = {}
    for completion in exercises_data:
        c_id = completion["id"]
        if c_id not in parsed_data.keys():
            parsed_data[c_id] = []
        parsed_data[c_id].append(
            {
                "date": completion["performed_at"],
                "dur": completion["performance_duration_in_seconds"],
                "err": completion["error_tally"],
            }
        )
        del c_id

    ex_pass_dates = []
    for key in parsed_data:
        error_free = []
        for occasion in parsed_data[key]:
            if (
                not isinstance(occasion["err"], int) or occasion["err"] == 0
            ):  # why err < 6 previously ?!
                error_free.append(occasion["date"])
        if len(error_free) > 0:
            ex_pass_dates.append(sorted(error_free)[0])

    if len(ex_pass_dates) < playlist_length:
        return None
    else:
        pl_pass_date_utc_str = sorted(ex_pass_dates)[-1]

    if make_concise_and_localize:  # for certain Django table renders
        # UTC is assumed here since the performed_at property is written to the performance database per UTC
        pl_pass_date = datetime.strptime(
            pl_pass_date_utc_str, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=pytz.timezone("UTC"))
        # for the user, interpret the pass_date in terms of the timezone for the course
        return datetime.strftime(
            pl_pass_date.astimezone(pytz.timezone(settings.TIME_ZONE)),
            "%Y_%m_%d (%a) %H:%M",
        )
    else:
        return pl_pass_date_utc_str


def playing_time(exercises_data):
    total_seconds = 0
    for completion in exercises_data:
        total_seconds += completion["performance_duration_in_seconds"]
        # data gives seconds down to 1/10 second
    total_seconds = int(total_seconds * 10) / 10
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds // 60) % 60)
    seconds = int((total_seconds // 1) % 60)
    if hours >= 2:
        return str(hours) + "+ hrs"
    elif hours == 1:
        return str(hours) + " hr, " + str(minutes) + " mins"
    elif minutes >= 1:
        return str(minutes) + "+ mins"
    else:
        return str(seconds) + "s"


def playlist_performance_view(request, performance_id):
    subscriber_id = request.user.id
    subscriber = get_object_or_404(User, id=subscriber_id)
    if not request.user.pk in subscriber.performance_permits:
        raise PermissionDenied
    performer_name = subscriber

    data = []
    performance = (
        PerformanceData.objects.filter(id=performance_id)
        .select_related("user", "playlist", "course")
        .first()
    )
    # performances = PerformanceData.objects.filter(
    #     playlist__id=playlist_id, user_id=subscriber_id
    # ).select_related("user", "playlist", "course")
    # playlist = Playlist.objects.get(id=playlist_id)
    exercises = [exercise for exercise in performance.playlist.exercise_list]

    course_id = getattr(performance.course, "id", None)
    course_name = "None"
    if course_id:
        course_name = Course.objects.get(id=course_id).title

    # performance_obj = performances.filter(user__email=user).first()
    # course = None
    # if performance_obj.course_id:
    #     course = Course.objects.get(_id=performance_obj.course_id)

    user_data = {
        "performer": subscriber,
        "subscriber_id": subscriber_id,
        "playlist_id": performance.playlist.id,
        "course_name": course_name,
        "course_id": course_id,
        "playlist_name": performance.playlist.name,
        "playlist_length": len(performance.playlist.exercise_list),
        "performance_obj": performance,
        "performance_data": performance.data,
        "performer_obj": subscriber,
    }
    user_data.update({"exercise_count": len(user_data["performance_data"])})
    data.append(user_data)

    for d in data:
        performance_obj = d["performance_obj"]
        exercises_data = d["performance_data"]

        d["playing_time"] = playing_time(exercises_data)
        d["playlist_pass_bool"] = playlist_pass_bool(
            exercises, exercises_data, d["playlist_length"]
        )  # why not len(exercises) ?!
        d["playlist_pass_date"] = playlist_pass_date(
            exercises, exercises_data, d["playlist_length"]
        )  # why not len(exercises) ?!

        for exercise in exercises_data:
            tempo_display_factor = 1
            # TODO: include time signature in the performance data for this purpose?
            # try:
            #     print(exercise)
            #     # get beat information from time signature
            #     time_sig = exercise["time_signature"]
            #     time_sig_numerator = int(time_sig.split("/")[0])
            #     tempo_display_factor = int(time_sig.split("/")[1])
            #     if time_sig_numerator > 3 and time_sig_numerator % 3 == 0:
            #         # compound meter
            #         tempo_display_factor /= 3
            #     try:
            #         float(tempo_display_factor)
            #     except ValueError:
            #         print("Unable to retrieve beat value from time signature")
            # except:
            #     print("Unable to retrieve beat value from time signature")

            d.update(
                **{
                    exercise["id"]: mark_safe(
                        f'{"PASS " + datetime.strftime(datetime.strptime(performance_obj.get_exercise_first_pass(exercise["id"]), "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone("UTC")).astimezone(pytz.timezone(settings.TIME_ZONE)), "%y_%m_%d %H:%M") + "<br><br>" if (performance_obj.get_exercise_first_pass(exercise["id"]) != False) else "TO DO<br><br>"}'
                        f'{"Latest: errors (" + str(exercise["error_tally"]) + ")." if (isinstance(exercise["error_tally"], int) and exercise["error_tally"] > 0) else ""}'
                        f'{"Done " if (isinstance(exercise["error_tally"], int) and exercise["error_tally"] == -1) else ""}'  # when is this shown?
                        f'{"Latest: without error." if (isinstance(exercise["error_tally"], int) and exercise["error_tally"] == 0) else ""}'
                        f'{"" if (isinstance(exercise["error_tally"], int) and exercise["error_tally"] > 0 or exercise["tempo_rating"] == None) else ["", "<br>Tempo erratic", "<br>Tempo unsteady", "<br>Tempo steady", "<br>Tempo very steady", "<br>Tempo perfectly steady"][round(exercise["tempo_rating"])]}'
                        f'{"" if (isinstance(exercise["error_tally"], int) and exercise["error_tally"] > 0 or "tempo_mean_semibreves_per_min" not in exercise) else "<br> at " + str(round(exercise["tempo_mean_semibreves_per_min"] * tempo_display_factor)) + " w.n.p.m.<br>"}'
                        f'<br><a href="{performance_obj.playlist.get_exercise_url_by_id(exercise["id"], course_id=course_id)}">Play again</a>'
                    )
                }
            )

    table = MyActivityDetailsTable(
        data=data,
        extra_columns=[
            (
                exercises[num],
                Column(
                    verbose_name=str(num + 1),
                    orderable=False,
                    default=mark_safe(
                        f'<a href="{performance_obj.playlist.get_exercise_url_by_num(num + 1, course_id=course_id)}">Try</a>'
                    ),
                ),
            )
            for num in range(len(exercises))
        ],
    )

    RequestConfig(request).configure(table)
    return render(
        request,
        "dashboard/performance_details.html",
        {"table": table, "performer_name": performer_name, "me": request.user},
    )
