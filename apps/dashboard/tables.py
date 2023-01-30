from django.contrib.auth import get_user_model
from django_tables2 import tables, A, columns
from django.db import models
from django.utils.html import format_html

User = get_user_model()


# Possible styling: attrs = {'class': 'table table-primary'}


class SupervisorsTable(tables.Table):
    name = tables.columns.Column(
        accessor=A("supervisor.get_full_name"),
        attrs={"td": {"width": "250px"}},
        verbose_name="Name of User",
    )
    supervisor = tables.columns.Column(
        attrs={"td": {"width": "250px"}}, verbose_name="Email Address of User"
    )
    status = tables.columns.Column(empty_values=())

    accept = tables.columns.LinkColumn(
        "dashboard:accept-subscription",
        empty_values=(),
        kwargs={
            "subscriber_id": A("user.id"),
            "supervisor_id": A("supervisor.id"),
        },
        verbose_name="Accept",
        orderable=False,
    )
    decline = tables.columns.LinkColumn(
        "dashboard:decline-subscription",
        empty_values=(),
        kwargs={
            "subscriber_id": A("user.id"),
            "supervisor_id": A("supervisor.id"),
        },
        verbose_name="Decline",
        orderable=False,
    )
    remove = tables.columns.LinkColumn(
        "dashboard:unsubscribe-confirmation",
        kwargs={"supervisor_id": A("supervisor.id")},
        text="Remove",
        verbose_name="Remove",
        orderable=False,
    )

    def render_status(self, record):
        return self.request.user._supervisors_dict[str(record["supervisor"].id)]

    def render_accept(self, record):
        if (
            self.request.user._supervisors_dict.get(str(record["supervisor"].id))
            == User.SUPERVISOR_STATUS_INVITATION_WAIT
        ):
            return "Accept"
        return ""

    def render_decline(self, record):
        if (
            self.request.user._supervisors_dict.get(str(record["supervisor"].id))
            == User.SUPERVISOR_STATUS_INVITATION_WAIT
        ):
            return "Decline"
        return ""

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class SubscribersTable(tables.Table):
    name = tables.columns.LinkColumn(
        "dashboard:subscriber-performances",
        kwargs={"subscriber_id": A("subscriber.id")},
        accessor=A("subscriber.get_full_name"),
        attrs={"td": {"width": "250px"}},
        verbose_name="Name of User",
    )
    subscriber = tables.columns.LinkColumn(
        "dashboard:subscriber-performances",
        kwargs={"subscriber_id": A("subscriber.id")},
        accessor=A("subscriber.email"),
        attrs={"td": {"width": "250px"}},
        verbose_name="Email Address of User",
    )
    status = tables.columns.Column(empty_values=())
    accept = tables.columns.LinkColumn(
        "dashboard:accept-subscription",
        empty_values=(),
        kwargs={
            "subscriber_id": A("subscriber.id"),
            "supervisor_id": A("user.id"),
        },
        verbose_name="Accept",
        orderable=False,
    )
    decline = tables.columns.LinkColumn(
        "dashboard:decline-subscription",
        empty_values=(),
        kwargs={
            "subscriber_id": A("subscriber.id"),
            "supervisor_id": A("user.id"),
        },
        verbose_name="Decline",
        orderable=False,
    )
    remove = tables.columns.LinkColumn(
        "dashboard:remove-subscriber-confirmation",
        kwargs={"subscriber_id": A("subscriber.id")},
        text="Remove",
        verbose_name="Remove",
        orderable=False,
    )

    def render_status(self, record):
        return record["subscriber"]._supervisors_dict[str(self.request.user.id)]

    def render_accept(self, record):
        if (
            record["subscriber"]._supervisors_dict[str(self.request.user.id)]
            == User.SUPERVISOR_STATUS_SUBSCRIPTION_WAIT
        ):
            return "Approve"
        return ""

    def render_decline(self, record):
        if (
            record["subscriber"]._supervisors_dict[str(self.request.user.id)]
            == User.SUPERVISOR_STATUS_SUBSCRIPTION_WAIT
        ):
            return "Decline"
        return ""

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class MyActivityTable(tables.Table):
    course = tables.columns.Column(
        verbose_name="Course title",
        accessor=("course.title"),
    )
    playlist = tables.columns.Column(
        verbose_name="Playlist name",
        # text=lambda record: record.playlist.name,
        accessor=("playlist.name"),
        # attrs={"td": {"bgcolor": "white", "width": "auto"}}
    )
    id = tables.columns.Column(
        verbose_name="ID",
        accessor=("playlist.id"),
    )
    playlist_passed = tables.columns.BooleanColumn(
        verbose_name="Passed",
        orderable=False,
    )
    playlist_pass_date = tables.columns.DateColumn(
        verbose_name="Pass Date",
        format="Y_m_d • D",
        orderable=False,  # ordering fails
    )
    view = tables.columns.LinkColumn(
        "dashboard:playlist-performance",
        kwargs={"performance_id": A("id")},
        text="Details",
        verbose_name="View Progress",
        orderable=False,
    )
    created = tables.columns.DateColumn(
        verbose_name="First attempt",
        format="Y_m_d • D",
        attrs={
            # "td": {"bgcolor": "white", "width": "auto"}
        },
    )
    updated = tables.columns.DateColumn(
        verbose_name="Latest attempt",
        format="Y_m_d • D",
        attrs={
            # "td": {"bgcolor": "white", "width": "auto"}
        },
    )

    # user
    # email

    def value_playlist_passed(self, record):
        return record.playlist_passed

    def render_playlist_pass_date(self, record):
        return record.playlist_pass_date

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        order_by = "-updated"
        template_name = "django_tables2/bootstrap4.html"


class MyActivityDetailsTable(tables.Table):
    playlist_name = tables.columns.Column(
        verbose_name="Playlist name",
        # orderable=False,
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    view = tables.columns.LinkColumn(
        "lab:playlist-view",
        kwargs={"course_id": A("course_id") or None, "playlist_id": A("playlist_id")},
        text="Play",
        verbose_name="Link",
        orderable=False,
    )
    id = tables.columns.Column(
        verbose_name="ID",
        accessor=("playlist_id"),
        # orderable=False,
        attrs={"td": {"bgcolor": "lightgray"}},
    )
    course_id = tables.columns.Column(
        verbose_name="ID",
        accessor=("course_id"),
        # orderable=False,
        attrs={"td": {"bgcolor": "lightgray"}},
    )
    exercise_count = tables.columns.Column(
        verbose_name="Tally", # tally of completions, including repeats
        orderable=False,
    )
    playing_time = tables.columns.Column(
        verbose_name="Time",
        orderable=False,
    )
    playlist_pass_bool = tables.columns.BooleanColumn(
        verbose_name="Passed",
        orderable=False,
    )
    playlist_pass_date = tables.columns.Column(
        verbose_name="... on date",
        orderable=False,
    )

    # performer_name = tables.columns.LinkColumn(
    #     'dashboard:subscriber-performances',
    #     kwargs={'subscriber_id': A('subscriber_id')},
    #     accessor=A('performer_obj.get_full_name'),
    #     attrs={"td": {"bgcolor": "white", "width": "auto"}},
    #     verbose_name='Performer Name'
    # )
    # performer = tables.columns.LinkColumn(
    #     'dashboard:subscriber-performances',
    #     kwargs={'subscriber_id': A('subscriber_id')},
    #     attrs={"td": {"bgcolor": "white", "width": "auto"}},
    #     verbose_name='Performer Email'
    # )

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
        sequence = (
            # 'performer_name', 'performer',
            "playlist_name",
            "view",
            "...",
            "id",
            "course_id",
            "exercise_count",
            "playing_time",
        )


class ExercisesListTable(tables.Table):
    id = tables.columns.Column()
    description = tables.columns.Column(
        verbose_name="Description of Exercise",
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    view = tables.columns.LinkColumn(
        "lab:exercise-view",
        kwargs={"exercise_id": A("id")},
        text="Preview",
        attrs={"a": {"target": "_blank"}},
        verbose_name="Preview",
        orderable=False,
    )

    edit = tables.columns.LinkColumn(
        "dashboard:edit-exercise",
        kwargs={"exercise_id": A("id")},
        text="Edit",
        verbose_name="Edit",
        orderable=False,
    )

    delete = tables.columns.LinkColumn(
        "dashboard:delete-exercise",
        kwargs={"exercise_id": A("id")},
        text="Delete",
        verbose_name="Delete",
        orderable=False,
    )
    created = tables.columns.DateColumn(
        verbose_name="Created",
        format="Y-m-d • h:i A",
    )
    updated = tables.columns.DateColumn(
        verbose_name="Modified",
        format="Y-m-d • h:i A",
    )
    is_public = tables.columns.BooleanColumn()

    def render_edit(self, record):
        if not record.has_been_performed:
            return "Edit"
        return "Edit*"

    def render_delete(self, record):
        if not record.has_been_performed:
            return "Delete"
        return ""

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        order_by = "-id"
        template_name = "django_tables2/bootstrap4.html"


class PlaylistsListTable(tables.Table):
    id = tables.columns.Column()
    name = tables.columns.Column(
        verbose_name="Name of Playlist",
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    view = tables.columns.LinkColumn(
        "lab:playlist-view",
        kwargs={"playlist_id": A("id")},
        text="Play",
        verbose_name="Play",
        orderable=False,
    )

    edit = tables.columns.LinkColumn(
        "dashboard:edit-playlist",
        kwargs={"playlist_id": A("id")},
        text="Edit",
        verbose_name="Edit",
        orderable=False,
    )

    delete = tables.columns.LinkColumn(
        "dashboard:delete-playlist",
        kwargs={"playlist_id": A("id")},
        text="Delete",
        verbose_name="Delete",
        orderable=False,
    )
    created = tables.columns.DateColumn(
        verbose_name="Created",
        format="Y-m-d • h:i A",
    )
    updated = tables.columns.DateColumn(
        verbose_name="Modified",
        format="Y-m-d • h:i A",
    )
    is_public = tables.columns.BooleanColumn()
    is_auto = tables.columns.BooleanColumn(verbose_name="Auto-Generated")

    def render_edit(self, record):
        if not record.has_been_performed:
            return "Edit"
        return "Edit*"

    def render_delete(self, record):
        if not record.has_been_performed:
            return "Delete"
        return ""

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        order_by = "-id"
        template_name = "django_tables2/bootstrap4.html"


class CoursesListTable(tables.Table):
    id = tables.columns.Column()
    title = tables.columns.Column(
        verbose_name="Title of Course",
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    activity = tables.columns.LinkColumn(
        "dashboard:course-activity",
        kwargs={"course_id": A("id")},
        text="Activity",
        verbose_name="Activity",
        orderable=False,
    )
    view = tables.columns.LinkColumn(
        "lab:course-view",
        kwargs={"course_id": A("id")},
        text="List of Playlists",
        verbose_name="List of Playlists",
        orderable=False,
    )

    edit = tables.columns.LinkColumn(
        "dashboard:edit-course",
        kwargs={"course_id": A("id")},
        text="Edit",
        verbose_name="Edit",
        orderable=False,
    )

    delete = tables.columns.LinkColumn(
        "dashboard:delete-course",
        kwargs={"course_id": A("id")},
        text="Delete",
        verbose_name="Delete",
        orderable=False,
    )
    created = tables.columns.DateColumn(
        verbose_name="Created",
        format="Y-m-d • h:i A",
    )
    updated = tables.columns.DateColumn(
        verbose_name="Modified",
        format="Y-m-d • h:i A",
    )
    is_public = tables.columns.BooleanColumn()

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        order_by = "-id"
        template_name = "django_tables2/bootstrap4.html"


class AvailableCoursesTable(tables.Table):
    title = tables.columns.Column(
        verbose_name="Title of Course",
    )
    view = tables.columns.LinkColumn(
        "lab:course-view",
        kwargs={"course_id": A("id")},
        text="List of Playlists",
        verbose_name="List of Playlists",
        orderable=False,
    )
    authored_by = tables.columns.Column()
    id = tables.columns.Column()

    # created = tables.columns.DateColumn(
    #     verbose_name='Created',
    #     format='Y-m-d • h:i A',
    # )
    # updated = tables.columns.DateColumn(
    #     verbose_name='Modified',
    #     format='Y-m-d • h:i A',
    # )
    # is_public = tables.columns.BooleanColumn()

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        order_by = ("authored_by", "title")
        template_name = "django_tables2/bootstrap4.html"


def val_to_order(value):
    if value == "P":
        return 0
    elif value == "T":
        return 1
    elif value == "L":
        return 2
    elif value == "X":
        return 3


c_element = '<span class="true no-due-date" title="Complete"></span>'
p_element = '<span class="true due-date-on-time" title="On time"></span>'
t_element = '<span class="true due-date-tardy" title=">=1 Hour Late"></span>'
l_element = '<span class="true due-date-late" title=">5 Days Late"></span>'
x_element = '<span class="false did-not-finish" title="Incomplete"></span>'
z_element = '<span class="false no-perf-data" title="No exercises played through"></span>'

class PlaylistActivityColumn(columns.Column):
    def render(self, value):
        if value == "C":
            element = c_element
        elif value == "P":
            element = p_element
        elif value == "T":
            element = t_element
        elif value == "L":
            element = l_element
        elif value == "X":
            element = x_element
        else:
            element = z_element
        return format_html(element)

    # TODO: get this working
    def order(self, queryset, is_descending):
        # queryset = queryset.annotate(
        #     priority=val_to_order()
        # ).order_by(("-" if is_descending else "") + "amount")
        return (queryset, True)


class CourseActivityTable(tables.Table):
    # TODO: make everything orderable again
    # subscriber_name = tables.columns.Column(verbose_name="Subscriber")
    subscriber_first_name = tables.columns.Column(verbose_name="Given name")
    subscriber_last_name = tables.columns.Column(verbose_name="Surname")
    # groups = tables.columns.Column(verbose_name="Group(s)")
    time_elapsed = tables.columns.Column(
        verbose_name="Time",
        orderable=True,
    )
    result_count = tables.columns.Column(
        verbose_name="Totaled Results",
        empty_values=(()),
        attrs={"td": {"style": "min-width:72px"}},
        orderable=False,
    )
    score = tables.columns.Column(
        verbose_name="Score",
        empty_values=(()),
        orderable=False, # does not work as currently configured
    )
    # subscriber_email = tables.columns.Column(
    #     verbose_name='Subscriber Email',
    # )
    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
        sequence = ["subscriber_first_name", "subscriber_last_name", "score", "result_count", "time_elapsed", "..."]

    def render_time_elapsed(self, value):
        try:
            hours_elapsed = value // 3600
        except:
            return ""
        mins_remainder = (value - 3600 * hours_elapsed) // 60
        readout_of_time_elapsed = (str(hours_elapsed) + "h " if hours_elapsed > 0 else "> ") + str(mins_remainder) + "m"
        return readout_of_time_elapsed

    def render_result_count(self, record):
        result_count = {"P": 0, "C": 0, "T": 0, "L": 0, "X": 0}
        for (key, value) in record.items():
            if value in result_count:
                result_count[value] += 1
        return format_html(
            f"{result_count['X']} {x_element} / {result_count['P']} {p_element} / {result_count['C']} {c_element} / {result_count['T']} {t_element} / {result_count['L']} {l_element}"
        )

    def render_score(self, record):
        tardy_credit = 0.8 # should be a variable in the course object
        late_credit = 0.5 # should be a variable in the course object
        result_count = {"P": 0, "C": 0, "T": 0, "L": 0, "X": 0}
        for (key, value) in record.items():
            if value in result_count:
                result_count[value] += 1
        score = result_count['P'] * result_count['C'] + result_count['T'] * tardy_credit * result_count['L'] * late_credit
        # make this column orderable
        return score


class GroupsListTable(tables.Table):
    name = tables.columns.Column()
    members = tables.columns.Column(accessor=A("members_count"))

    edit = tables.columns.LinkColumn(
        "dashboard:edit-group",
        kwargs={"group_id": A("id")},
        text="Edit",
        verbose_name="Edit",
        orderable=False,
    )

    delete = tables.columns.LinkColumn(
        "dashboard:delete-group",
        kwargs={"group_id": A("id")},
        text="Delete",
        verbose_name="Delete",
        orderable=False,
    )

    created = tables.columns.DateColumn(
        verbose_name="Created",
        format="Y-m-d • h:i A",
    )
    updated = tables.columns.DateColumn(
        verbose_name="Modified",
        format="Y-m-d • h:i A",
    )

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class GroupMembersTable(tables.Table):
    member_name = tables.columns.Column(
        accessor=A("member.get_full_name"),
        attrs={"td": {"width": "250px"}},
        verbose_name="Name of User",
    )
    member_email = tables.columns.Column(
        accessor=A("member.email"),
        attrs={"td": {"width": "250px"}},
        verbose_name="Email Address of User",
    )
    subscription_status = tables.columns.Column(
        empty_values=(), verbose_name="Subscription Status"
    )

    remove = tables.columns.LinkColumn(
        "dashboard:remove-group-member",
        kwargs={"group_id": A("group_id"), "member_id": A("member.id")},
        text="Remove",
        verbose_name="Remove",
        orderable=False,
    )

    def render_subscription_status(self, record):
        return record["member"]._supervisors_dict[str(self.request.user.id)]

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
