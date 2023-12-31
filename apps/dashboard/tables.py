from django.contrib.auth import get_user_model
from django_tables2 import tables, A, columns
from django.db import models
from django.utils.html import format_html
from django.contrib.postgres.fields.jsonb import KeyTextTransform

User = get_user_model()


# Possible styling: attrs = {'class': 'table table-primary'}


class ConnectionsTable(tables.Table):
    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"

    email = tables.columns.Column(
        accessor=A("other.email"),
        attrs={"td": {"width": "250px"}},
        verbose_name="Email address",
    )
    first_name = tables.columns.Column(
        accessor=A("other.first_name"), verbose_name="Given name"
    )
    last_name = tables.columns.Column(
        accessor=A("other.last_name"), verbose_name="Surname"
    )
    signup_date = tables.columns.Column(
        accessor=A("other.date_joined"), verbose_name="User signup date"
    )
    toggle_content_permit = tables.columns.LinkColumn(
        "dashboard:toggle-content-permit",
        empty_values=(),
        kwargs={"other_id": A("other.id")},
        verbose_name="Content permit",
        orderable=False,
    )
    toggle_performance_permit = tables.columns.LinkColumn(
        "dashboard:toggle-performance-permit",
        empty_values=(),
        kwargs={"other_id": A("other.id")},
        verbose_name="Performance permit",
        orderable=False,
    )
    content_access = tables.columns.LinkColumn(
        "dashboard:courses-by-user",
        kwargs={"courses_author_id": A("other.id")},
        verbose_name="Access content",
        text="Courses",
        orderable=False,
    )
    performance_access = tables.columns.LinkColumn(
        "dashboard:performances-by-user",
        kwargs={"other_id": A("other.id")},
        verbose_name="Access performances",
        text="Performances",
        orderable=False,
    )
    pinned = tables.columns.LinkColumn(
        "dashboard:toggle-connection-pin",
        empty_values=(),
        kwargs={"other_id": A("other.id")},
        verbose_name="Pinned",
        orderable=False,
    )

    def render_last_name(self, record):
        if (
            self.request.user.id in record["other"].content_permits
            or self.request.user.id in record["other"].performance_permits
        ):
            return record["other"].last_name
        else:
            return ""

    def render_first_name(self, record):
        if (
            self.request.user.id in record["other"].content_permits
            or self.request.user.id in record["other"].performance_permits
        ):
            return record["other"].first_name
        else:
            return ""

    def render_signup_date(self, record):
        if (
            self.request.user.id in record["other"].content_permits
            or self.request.user.id in record["other"].performance_permits
        ):
            return record["other"].date_joined
        else:
            return ""

    def render_toggle_content_permit(self, record):
        if int(record["other"].id) in self.request.user.content_permits:
            return "YES"
        else:
            return "no"
        return ""

    def render_toggle_performance_permit(self, record):
        if int(record["other"].id) in self.request.user.performance_permits:
            return "YES"
        else:
            return "no"
        return ""

    def render_content_access(self, record):
        if self.request.user.id in record["other"].content_permits:
            return "Courses"
        return ""

    def render_performance_access(self, record):
        if self.request.user.id in record["other"].performance_permits:
            return "Performances"
        return ""

    def render_pinned(self, record):
        if int(record["other"].id) in self.request.user.connections_list:
            return "YES"
        else:
            return "no"
        return ""

    # Note: Ordering based on non-database fields appears impossible
    # according to this: https://github.com/jieter/django-tables2/issues/161
    # def order_status(self, queryset, is_descending):
    #     queryset = queryset.annotate(
    #         priority=
    #     ).order_by(("-" if is_descending else "") + "priority")
    #     return (queryset, True)


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
        kwargs={"course_id": A("course.id") or None, "playlist_id": A("playlist.id")},
        verbose_name="Playlist name",
        accessor=("playlist.name"),
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
    created = tables.columns.DateColumn(
        verbose_name="Earliest activity",
        format="Y_m_d (D) H:i",  # "Y_m_d • D"
    )
    updated = tables.columns.DateColumn(
        verbose_name="Latest activity",
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
        # orderable=False, # keep it orderable in order for seamless viewing with MyActivity
        # attrs={"td": {"bgcolor": "lightgray"}},
    )
    playlist_id = tables.columns.Column(
        verbose_name="C-ID",
        accessor=("playlist_id"),
        # orderable=False, # keep it orderable in order for seamless viewing with MyActivity
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
    #     accessor=A('performer.first_name'),
    #     verbose_name='Given name'
    # )
    # performer_surname = tables.columns.Column(
    #     accessor=A('performer.last_name'),
    #     verbose_name='Surname'
    # )
    # performer_email = tables.columns.LinkColumn(
    #     'dashboard:performances-by-user',
    #     kwargs={'other_id': A('other_id')},
    #     accessor=A('performer.email'),
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
        verbose_name="Exercise description",
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
        "dashboard:delete-exercise",
        kwargs={"exercise_id": A("id")},
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
    course_id = tables.columns.Column(
        verbose_name="C-ID",
        accessor=A("id"),
    )
    view = tables.columns.LinkColumn(
        # text="List of Playlists", # formerly
        "lab:course-view",
        kwargs={"course_id": A("id")},
        verbose_name="Course name",
        accessor=A("title"),
    )
    # course_name = tables.columns.Column(
    #     verbose_name="Course name",
    #     accessor=A("title"),
    # )
    activity = tables.columns.LinkColumn(
        "dashboard:course-activity",
        kwargs={"course_id": A("id")},
        text="Activity",
        verbose_name="Performance activity",
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
        order_by = "-course_id"
        template_name = "django_tables2/bootstrap4.html"


class CoursesByOthersTable(tables.Table):
    course_id = tables.columns.Column(
        verbose_name="C-ID",
        accessor=A("id"),
    )
    authored_by = tables.columns.Column()
    view = tables.columns.LinkColumn(
        # text="List of Playlists", # formerly
        "lab:course-view",
        kwargs={"course_id": A("id")},
        verbose_name="Course name",
        accessor=A("title"),
    )
    # title = tables.columns.Column(
    #     verbose_name="Course name",
    # )

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
        order_by = ("authored_by", "view")
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
    # performer_email = tables.columns.Column(
    #     verbose_name='Email',
    # )
    performer_first_name = tables.columns.Column(verbose_name="Given name")
    performer_last_name = tables.columns.Column(verbose_name="Surname")
    # groups = tables.columns.Column(verbose_name="Group(s)")
    time_elapsed = tables.columns.Column(
        verbose_name="Time (beta)",
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

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
        sequence = [
            "performer_first_name",
            "performer_last_name",
            "score",
            "result_count",
            "time_elapsed",
            "...",
        ]

    def __init__(self, course, **kwargs):
        self.course = course
        super().__init__(**kwargs)

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
        for key, value in record.items():
            if value in result_count:
                result_count[value] += 1
        return format_html(
            f"{result_count['X']} {x_element} / {result_count['P']} {p_element} / {result_count['C']} {c_element} / {result_count['T']} {t_element} / {result_count['L']} {l_element}"
        )

    def render_score(self, record):
        timely_credit = self.course.timely_credit
        tardy_credit = self.course.tardy_credit
        late_credit = self.course.late_credit
        result_count = {"P": 0, "C": 0, "T": 0, "L": 0, "X": 0}
        for key, value in record.items():
            if value in result_count:
                result_count[value] += 1
        score = (
            result_count["P"] * timely_credit
            + result_count["C"] * timely_credit
            + result_count["T"] * tardy_credit
            + result_count["L"] * late_credit
        )
        # make this column orderable
        return round(score, 1)


class GroupsListTable(tables.Table):
    name = tables.columns.Column()
    members = tables.columns.Column(
        accessor=A("members_count"),
        verbose_name="Members",
    )
    edit = tables.columns.LinkColumn(
        "dashboard:edit-group",
        kwargs={"group_id": A("id")},
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
    delete = tables.columns.LinkColumn(
        "dashboard:delete-group",
        kwargs={"group_id": A("id")},
        text="Delete",
        verbose_name="Delete",
        orderable=False,
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
        verbose_name="Email address",
    )
    performance_access = tables.columns.Column(
        empty_values=(), verbose_name="Performance Access"
    )

    remove = tables.columns.LinkColumn(
        "dashboard:remove-group-member",
        kwargs={"group_id": A("group_id"), "member_id": A("member.id")},
        text="Disconnect",
        verbose_name="Disconnect",
        orderable=False,
    )

    def render_performance_access(self, record):
        return self.request.user.id in record["member"].performance_permits

    class Meta:
        attrs = {"class": "paleblue"}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
