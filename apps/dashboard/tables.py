from django.contrib.auth import get_user_model
from django_tables2 import tables, A, columns
from django.db import models
from django.utils.html import format_html
from django.contrib.postgres.fields.jsonb import KeyTextTransform

User = get_user_model()


# Possible styling: attrs = {'class': 'table table-primary'}


class SupervisorsTable(tables.Table):

    first_name = tables.columns.Column(
        accessor=A("supervisor.first_name"), verbose_name="Given name"
    )
    last_name = tables.columns.Column(
        accessor=A("supervisor.last_name"), verbose_name="Surname"
    )

    # name = tables.columns.Column(
    #     accessor=A("supervisor.get_full_name"),
    #     attrs={"td": {"width": "250px"}},
    #     verbose_name="Name of User",
    # )
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


status_order_dict = {
    User.SUPERVISOR_STATUS_INVITATION_WAIT: 0,
    User.SUPERVISOR_STATUS_ACCEPTED: 1,
    User.SUPERVISOR_STATUS_DECLINED: 2,
}


class SubscribersTable(tables.Table):
    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"

    first_name = tables.columns.Column(
        accessor=A("subscriber.first_name"), verbose_name="Given name"
    )
    last_name = tables.columns.Column(
        accessor=A("subscriber.last_name"), verbose_name="Surname"
    )

    # name = tables.columns.LinkColumn(
    #     "dashboard:subscriber-performances",
    #     kwargs={"subscriber_id": A("subscriber.id")},
    #     accessor=A("subscriber.get_full_name"),
    #     attrs={"td": {"width": "250px"}},
    #     verbose_name="Name of User",
    # )
    email = tables.columns.Column(
        accessor=A("subscriber.email"),
        attrs={"td": {"width": "250px"}},
        verbose_name="Email Address of User",
    )
    performances = tables.columns.LinkColumn(
        "dashboard:subscriber-performances",
        text="View Performances",
        kwargs={"subscriber_id": A("subscriber.id")},
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

    signup_date = tables.columns.Column(
        accessor=A("subscriber.date_joined"), verbose_name="Signup Date"
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

    def render_performances(self, record):
        if (
            record["subscriber"]._supervisors_dict[str(self.request.user.id)]
            == User.SUPERVISOR_STATUS_ACCEPTED
        ):
            return "Performances"
        return ""

    # TODO: revisit this. ordering based on non-database fields appears impossible
    #   according to this: https://github.com/jieter/django-tables2/issues/161
    def order_status(self, queryset, is_descending):
        queryset = queryset.annotate(
            # Annotates each subscriber with their subscription status with the current user,
            #  put into the status_order_dict for custom order instead of alphabetical
            priority=status_order_dict.get(
                KeyTextTransform(str(self.request.user.id), "_supervisors_dict"), -1
            )
        ).order_by(("-" if is_descending else "") + "priority")
        return (queryset, True)


class MyActivityTable(tables.Table):
    course_name = tables.columns.LinkColumn(
        "lab:course-view",
        kwargs={"course_id": A("course.id")},
        verbose_name="Course name",
        accessor=("course.title"),
        # attrs={"td": {"style": "white-space:nowrap", "width": "auto"}}
    )
    playlist = tables.columns.LinkColumn(
        "lab:playlist-view",
        kwargs={"course_id": A("course.id"), "playlist_id": A("playlist.id")},
        verbose_name="Playlist name",
        # attrs={"td": {"style": "white-space:nowrap", "width": "auto"}}
    )
    playlist_passed = tables.columns.BooleanColumn(
        verbose_name="Passed",
        orderable=False,  # ordering fails
    )
    playlist_pass_date = tables.columns.DateColumn(
        verbose_name="Pass Date",
        format="Y_m_d (D) H:i",  # ineffective
        orderable=False,  # ordering fails
    )
    course_id = tables.columns.Column(
        verbose_name="C-ID",
        accessor=("course.id"),
        # attrs={"td": {"bgcolor": "lightgray"}},
    )
    playlist_id = tables.columns.Column(
        verbose_name="P-ID",
        accessor=("playlist.id"),
        # attrs={"td": {"bgcolor": "lightgray"}},
    )
    view = tables.columns.LinkColumn(
        "dashboard:playlist-performance",
        kwargs={"performance_id": A("id")},
        text="+ Details",
        verbose_name="Navigation",
        orderable=False,
    )
    updated = tables.columns.DateColumn(
        verbose_name="Latest activity",
        format="Y_m_d (D) H:i",  # "Y_m_d • D"
    )
    created = tables.columns.DateColumn(
        verbose_name="Earliest activity",
        format="Y_m_d (D) H:i",  # "Y_m_d • D"
    )
    # USEFUL FOR INSTRUCTOR VIEWS YET TO BE ADDED
    # add performer_given_name, performer_surname, performer_email
    # like in MyActivityTable

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
    course_name = tables.columns.LinkColumn(
        "lab:course-view",
        kwargs={"course_id": A("course_id")},
        verbose_name="Course name",
        accessor=A("course_name"),
        empty_values=(),  # only needed if no reliable accessor
        # orderable=False, # keep it orderable in order for seamless viewing with MyActivity
    )
    playlist_name = tables.columns.LinkColumn(
        "lab:playlist-view",
        kwargs={"course_id": A("course_id") or None, "playlist_id": A("playlist_id")},
        verbose_name="Playlist name",
        # orderable=False, # keep it orderable in order for seamless viewing with MyActivity
    )
    playlist_pass_bool = tables.columns.BooleanColumn(
        verbose_name="Passed",
        orderable=False,
    )
    playlist_pass_date = tables.columns.Column(
        verbose_name="Pass Date",
        orderable=False,
    )
    view = tables.columns.LinkColumn(
        "dashboard:performed-playlists",
        text="- Details",
        verbose_name="Navigation",
        orderable=False,
    )
    exercise_count = tables.columns.Column(
        verbose_name="Tally",  # tally of completions, including repeats
        orderable=False,
    )
    playing_time = tables.columns.Column(
        verbose_name="Clock",
        orderable=False,
    )
    course_id = tables.columns.Column(
        verbose_name="P-ID",
        accessor=("course_id"),
        orderable=False,
        # attrs={"td": {"bgcolor": "lightgray"}},
    )
    playlist_id = tables.columns.Column(
        verbose_name="C-ID",
        accessor=("playlist_id"),
        orderable=False,
        # attrs={"td": {"bgcolor": "lightgray"}},
    )
    # add updated, created
    # like in MyActivityTable

    def value_view(self, record):
        self.text = record.playlist_name

    def render_course_name(self, record):
        try:
            return record["course_name"]
        except:
            return "ID: " + record["course_id"]

    # USEFUL FOR INSTRUCTOR VIEWS YET TO BE ADDED
    # performer_given_name = tables.columns.Column(
    #     accessor=A('performer_obj.first_name'),
    #     verbose_name='Given name'
    # )
    # performer_surname = tables.columns.Column(
    #     accessor=A('performer_obj.last_name'),
    #     verbose_name='Surname'
    # )
    # performer_email = tables.columns.LinkColumn(
    #     'dashboard:subscriber-performances',
    #     kwargs={'subscriber_id': A('subscriber_id')},
    #     accessor=A('performer_obj.email'),
    #     verbose_name='User email'
    # )

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
        sequence = (
            "course_name",
            "playlist_name",
            "playlist_pass_bool",
            "playlist_pass_date",
            "playlist_id",
            "course_id",
            "view",
            "playing_time",
            "exercise_count",
            "...",
            # "performer_given_name",
            # "performer_surname",
            # "performer_email",
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
        verbose_name="Playlist name",
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    view = tables.columns.LinkColumn(
        "lab:playlist-view",
        kwargs={"playlist_id": A("id")},
        text="Preview",
        verbose_name="Preview",
        orderable=False,
    )

    edit = tables.columns.LinkColumn(
        "dashboard:edit-playlist",
        kwargs={"playlist_id": A("id")},
        text="Edit",
        verbose_name="Edit",
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
    delete = tables.columns.LinkColumn(
        "dashboard:delete-playlist",
        kwargs={"playlist_id": A("id")},
        text="Delete",
        verbose_name="Delete",
        orderable=False,
    )

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
    view = tables.columns.LinkColumn(
        # text="List of Playlists", # formerly
        "lab:course-view",
        kwargs={"course_id": A("id")},
        accessor=A("id"),
        verbose_name="C-ID",
    )
    # course_id = tables.columns.Column(
    #     verbose_name="C-ID",
    #     accessor=A("id"),
    # )
    course_name = tables.columns.Column(
        verbose_name="Course name",
        accessor=A("title"),
    )
    activity = tables.columns.LinkColumn(
        "dashboard:course-activity",
        kwargs={"course_id": A("id")},
        text="see activity",
        verbose_name="Performance Activity",
        orderable=False,
    )

    edit = tables.columns.LinkColumn(
        "dashboard:edit-course",
        kwargs={"course_id": A("id")},
        text="Edit",
        verbose_name="Edit",
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
    delete = tables.columns.LinkColumn(
        "dashboard:delete-course",
        kwargs={"course_id": A("id")},
        text="Delete",
        verbose_name="Delete",
        orderable=False,
    )

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
z_element = (
    '<span class="false no-perf-data" title="No exercises played through"></span>'
)


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
        attrs={"td": {"style": "white-space:nowrap"}},
        orderable=True,
    )
    result_count = tables.columns.Column(
        verbose_name="Totaled Results",
        empty_values=(()),
        attrs={"td": {"style": "white-space:nowrap"}},
        orderable=False,
    )
    score = tables.columns.Column(
        verbose_name="Score",
        empty_values=(()),
        orderable=False,  # does not work as currently configured
    )
    # subscriber_email = tables.columns.Column(
    #     verbose_name='Subscriber Email',
    # )
    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
        sequence = [
            "subscriber_first_name",
            "subscriber_last_name",
            "score",
            "result_count",
            "time_elapsed",
            "...",
        ]

    def render_time_elapsed(self, value):
        hours = value // 3600
        minutes = (value // 60) % 60
        seconds = (value // 1) % 60

        rendered_time = ""
        if hours == 1:
            rendered_time += str(hours) + " hr "
        if hours > 1:
            rendered_time += str(hours) + " hrs "
        rendered_time += str(minutes) + " min"
        if hours == 0:
            rendered_time += " " + str(seconds) + " sec"
        return rendered_time

    def render_result_count(self, record):
        result_count = {"P": 0, "C": 0, "T": 0, "L": 0, "X": 0}
        for (key, value) in record.items():
            if value in result_count:
                result_count[value] += 1
        return format_html(
            f"{result_count['X']} {x_element} / {result_count['P']} {p_element} / {result_count['C']} {c_element} / {result_count['T']} {t_element} / {result_count['L']} {l_element}"
        )

    def render_score(self, record):
        tardy_credit = 0.8  # should be a variable in the course object
        late_credit = 0.5  # should be a variable in the course object
        result_count = {"P": 0, "C": 0, "T": 0, "L": 0, "X": 0}
        for (key, value) in record.items():
            if value in result_count:
                result_count[value] += 1
        score = (
            result_count["P"]
            + result_count["C"]
            + result_count["T"] * tardy_credit
            + result_count["L"] * late_credit
        )
        # make this column orderable
        return round(score, 1)


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
