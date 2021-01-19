from django.contrib.auth import get_user_model
from django_tables2 import tables, A
from django.db import models

User = get_user_model()

# Possible styling: attrs = {'class': 'table table-primary'}

class SupervisorsTable(tables.Table):
    name = tables.columns.Column(
        accessor=A('supervisor.get_full_name'),
        attrs={"td": {"width": "250px"}},
        verbose_name='Name of User'
    )
    supervisor = tables.columns.Column(
        attrs={"td": {"width": "250px"}},
        verbose_name='Email Address of User'
    )
    status = tables.columns.Column(empty_values=())

    accept = tables.columns.LinkColumn('dashboard:accept-subscription', empty_values=(),
                                       kwargs={
                                           'subscriber_id': A('user.id'),
                                           'supervisor_id': A('supervisor.id'),
                                       },
                                       verbose_name='Accept', orderable=False)
    decline = tables.columns.LinkColumn('dashboard:decline-subscription', empty_values=(),
                                        kwargs={
                                            'subscriber_id': A('user.id'),
                                            'supervisor_id': A('supervisor.id'),
                                        },
                                       verbose_name='Decline', orderable=False)
    remove = tables.columns.LinkColumn('dashboard:unsubscribe',
                                       kwargs={'supervisor_id': A('supervisor.id')},
                                       text='Remove', verbose_name='Remove', orderable=False)

    def render_status(self, record):
        return self.request.user._supervisors_dict[str(record['supervisor'].id)]

    def render_accept(self, record):
        if self.request.user._supervisors_dict.get(str(record['supervisor'].id)) == User.SUPERVISOR_STATUS_INVITATION_WAIT:
            return 'Accept'
        return ''

    def render_decline(self, record):
        if self.request.user._supervisors_dict.get(str(record['supervisor'].id)) == User.SUPERVISOR_STATUS_INVITATION_WAIT:
            return 'Decline'
        return ''

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class SubscribersTable(tables.Table):
    name = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                     kwargs={'subscriber_id': A('subscriber.id')},
                                     accessor=A('subscriber.get_full_name'),
                                     attrs={"td": {"width": "250px"}},
                                     verbose_name='Name of User')
    subscriber = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                           kwargs={'subscriber_id': A('subscriber.id')},
                                           attrs={"td": {"width": "250px"}},
                                           verbose_name='Email Address of User')
    status = tables.columns.Column(empty_values=())
    accept = tables.columns.LinkColumn('dashboard:accept-subscription', empty_values=(),
                                       kwargs={
                                           'subscriber_id': A('subscriber.id'),
                                           'supervisor_id': A('user.id'),
                                       },
                                       verbose_name='Accept', orderable=False)
    decline = tables.columns.LinkColumn('dashboard:decline-subscription', empty_values=(),
                                        kwargs={
                                            'subscriber_id': A('subscriber.id'),
                                            'supervisor_id': A('user.id'),
                                        },
                                        verbose_name='Decline', orderable=False)
    remove = tables.columns.LinkColumn('dashboard:remove-subscriber',
                                       kwargs={'subscriber_id': A('subscriber.id')},
                                       text='Remove', verbose_name='Remove', orderable=False)

    def render_status(self, record):
        return record['subscriber']._supervisors_dict[str(self.request.user.id)]

    def render_accept(self, record):
        if record['subscriber']._supervisors_dict[str(self.request.user.id)] == User.SUPERVISOR_STATUS_SUBSCRIPTION_WAIT:
            return 'Approve'
        return ''

    def render_decline(self, record):
        if record['subscriber']._supervisors_dict[str(self.request.user.id)] == User.SUPERVISOR_STATUS_SUBSCRIPTION_WAIT:
            return 'Decline'
        return ''

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class MyActivityTable(tables.Table):
    playlist = tables.columns.Column(
        verbose_name='Playlist name',
        # text=lambda record: record.playlist.name,
        accessor=('playlist.name'),
        # attrs={"td": {"bgcolor": "white", "width": "auto"}}
    )
    id = tables.columns.Column(
        verbose_name='ID',
        accessor=('playlist.id'),
    )
    playlist_passed = tables.columns.BooleanColumn(
        verbose_name='Passed',
        orderable=False,
    )
    playlist_pass_date = tables.columns.DateColumn(
        verbose_name='Pass Date',
        format='Y_m_d • D',
        orderable=False,
    )
    view = tables.columns.LinkColumn(
        'dashboard:subscriber-playlist-performance',
        kwargs={
            'playlist_id': A('playlist.id'),
            'subscriber_id': A('user.id')
        },
        text='Details',
        verbose_name='View Progress',
        orderable=False
    )
    created = tables.columns.DateColumn(
        verbose_name='First attempt',
        format='Y_m_d • D',
        attrs={
            # "td": {"bgcolor": "white", "width": "auto"}
        }
    )
    updated = tables.columns.DateColumn(
        verbose_name='Latest attempt',
        format='Y_m_d • D',
        attrs={
            # "td": {"bgcolor": "white", "width": "auto"}
        }
    )
    # user
    # email

    def render_playlist_passed(self, record):
        return record.playlist_passed

    def render_playlist_pass_date(self, record):
        return record.playlist_pass_date

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        order_by = ('-updated')
        template_name = "django_tables2/bootstrap4.html"


class MyActivityDetailsTable(tables.Table):
    playlist_name = tables.columns.Column(
        verbose_name='Playlist name',
        orderable=False,
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    view = tables.columns.LinkColumn(
        'lab:playlist-view',
        kwargs={'playlist_name': A('playlist_name')},
        text='Revisit',
        verbose_name='Load',
        orderable=False
    )
    id = tables.columns.Column(
        verbose_name='ID',
        accessor=('playlist_id'),
        orderable=False,
        attrs={"td": {"bgcolor": "lightgray"}}
    )
    exercise_count = tables.columns.Column(
        verbose_name='Tally of finished exercises',
        orderable=False,
    )
    playing_time = tables.columns.Column(
        verbose_name='Playing time',
        orderable=False,
    )
    playlist_pass_bool = tables.columns.BooleanColumn(
        verbose_name='Passed',
        orderable=False,
    )
    playlist_pass_date = tables.columns.Column(
        verbose_name='Pass date',
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
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
        sequence = (
            # 'performer_name', 'performer',
            'playlist_name', 'view',
            '...',
            'id',
            'exercise_count',
        )


class ExercisesListTable(tables.Table):
    id = tables.columns.Column()
    name = tables.columns.Column(
        verbose_name='Description of Exercise',
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    view = tables.columns.LinkColumn('lab:exercise-view',
                                     kwargs={'exercise_id': A('id')},
                                     text='Load', verbose_name='Load', orderable=False)

    edit = tables.columns.LinkColumn('dashboard:edit-exercise',
                                     kwargs={'exercise_id': A('id')},
                                     text='Edit', verbose_name='Edit', orderable=False)

    delete = tables.columns.LinkColumn('dashboard:delete-exercise',
                                       kwargs={'exercise_id': A('id')},
                                       text='Delete', verbose_name='Delete', orderable=False)
    created = tables.columns.DateColumn(
        verbose_name='Created',
        format='Y-m-d • h:m A',
    )
    updated = tables.columns.DateColumn(
        verbose_name='Modified',
        format='Y-m-d • h:m A',
    )
    is_public = tables.columns.BooleanColumn()

    def render_edit(self, record):
        if not record.has_been_performed:
            return 'Edit'
        return 'View'

    def render_delete(self, record):
        if not record.has_been_performed:
            return 'Delete'
        return ''

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        order_by = ('-id')
        template_name = "django_tables2/bootstrap4.html"


class PlaylistsListTable(tables.Table):
    name = tables.columns.Column(
        verbose_name='Name of Playlist',
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    id = tables.columns.Column()
    view = tables.columns.LinkColumn('lab:playlist-view',
                                     kwargs={'playlist_name': A('name')},
                                     text='Load', verbose_name='Load', orderable=False)

    edit = tables.columns.LinkColumn('dashboard:edit-playlist',
                                     kwargs={'playlist_name': A('name')},
                                     text='Edit', verbose_name='Edit', orderable=False)

    delete = tables.columns.LinkColumn('dashboard:delete-playlist',
                                       kwargs={'playlist_name': A('name')},
                                       text='Delete', verbose_name='Delete', orderable=False)
    created = tables.columns.DateColumn(
        verbose_name='Created',
        format='Y-m-d • h:m A',
    )
    updated = tables.columns.DateColumn(
        verbose_name='Modified',
        format='Y-m-d • h:m A',
    )
    is_public = tables.columns.BooleanColumn()

    def render_edit(self, record):
        if not record.has_been_performed:
            return 'Edit'
        return 'View'

    def render_delete(self, record):
        if not record.has_been_performed:
            return 'Delete'
        return ''

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        order_by = ('-id')
        template_name = "django_tables2/bootstrap4.html"


class CoursesListTable(tables.Table):
    title = tables.columns.Column(
        verbose_name='Title of Course',
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    id = tables.columns.Column()
    view = tables.columns.LinkColumn('lab:course-view',
                                     kwargs={'course_slug': A('slug')},
                                     text='Load', verbose_name='Load', orderable=False)

    edit = tables.columns.LinkColumn('dashboard:edit-course',
                                     kwargs={'course_name': A('title')},
                                     text='Edit', verbose_name='Edit', orderable=False)

    delete = tables.columns.LinkColumn('dashboard:delete-course',
                                       kwargs={'course_name': A('title')},
                                       text='Delete', verbose_name='Delete', orderable=False)
    created = tables.columns.DateColumn(
        verbose_name='Created',
        format='Y-m-d • h:m A',
    )
    updated = tables.columns.DateColumn(
        verbose_name='Modified',
        format='Y-m-d • h:m A',
    )
    is_public = tables.columns.BooleanColumn()

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        order_by = ('-id')
        template_name = "django_tables2/bootstrap4.html"
