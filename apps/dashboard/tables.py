from django.contrib.auth import get_user_model
from django_tables2 import tables, A

User = get_user_model()


class SupervisorsTable(tables.Table):
    name = tables.columns.Column(
        accessor=A('supervisor.get_full_name'),
        attrs={"td": {"width": "250px"}},
        verbose_name='Name of Supervisor'
    )
    supervisor = tables.columns.Column(
        attrs={"td": {"width": "250px"}},
        verbose_name='Email Address of Supervisor'
    )
    remove = tables.columns.LinkColumn('dashboard:unsubscribe',
                                       kwargs={'supervisor_id': A('supervisor.id')},
                                       text='Remove', verbose_name='Remove', orderable=False)

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class SubscribersTable(tables.Table):
    name = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                     kwargs={'subscriber_id': A('subscriber.id')},
                                     accessor=A('subscriber.get_full_name'),
                                     attrs={"td": {"width": "250px"}},
                                     verbose_name='Name of Subscriber')
    subscriber = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                           kwargs={'subscriber_id': A('subscriber.id')},
                                           attrs={"td": {"width": "250px"}},
                                           verbose_name='Email Address of Subscriber')
    remove = tables.columns.LinkColumn('dashboard:remove-subscriber',
                                       kwargs={'subscriber_id': A('subscriber.id')},
                                       text='Remove', verbose_name='Remove', orderable=False)

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class MyActivityTable(tables.Table):
    playlist = tables.columns.Column(
        verbose_name='Name of Playlist',
        # text=lambda record: record.playlist.name,
        accessor=('playlist.name'),
        # attrs={"td": {"bgcolor": "white", "width": "auto"}}
    )
    id = tables.columns.Column(
        verbose_name='ID',
        accessor=('playlist.id'),
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
    # playlist_pass_bool = tables.columns.Column(
    #     verbose_name='Playlist passed'
    # )
    # pass_date = tables.columns.Column(
    #     verbose_name='Pass date'
    # )
    created = tables.columns.DateColumn(
        verbose_name='Begun',
        format='Y-m-d • l',
        attrs={
            # "td": {"bgcolor": "white", "width": "auto"}
        }
    )
    updated = tables.columns.DateColumn(
        verbose_name='Latest activity',
        format='Y-m-d • l',
        attrs={
            # "td": {"bgcolor": "white", "width": "auto"}
        }
    )
    # data = tables.columns.Column(
    #     verbose_name='Progress',
    #     accessor='data.0',
    # )
    # user = tables.columns.LinkColumn(
    #   'dashboard:subscriber-performances',
    #   verbose_name='Performer Name',
    #   kwargs={
    #     'subscriber_id': A('user.id')
    #   },
    #   accessor=A('user.get_full_name'),
    #   attrs={
    #     "td": {"bgcolor": "white", "width": "auto"}
    #   }
    # )
    # email = tables.columns.LinkColumn(
    #     'dashboard:subscriber-performances',
    #     verbose_name='Performer Email',
    #     kwargs={
    #         'subscriber_id': A('user.id')
    #     },
    #     accessor=A('user.email'),
    #     attrs={
    #         "td": {"bgcolor": "white", "width": "auto"}
    #     }
    # )

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        order_by = ('-created')
        template_name = "django_tables2/bootstrap4.html"


class MyActivityDetailsTable(tables.Table):
    playlist_name = tables.columns.Column(
        verbose_name='Name of Playlist',
        orderable=False,
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
    )
    view = tables.columns.LinkColumn(
        'lab:exercise-groups',
        kwargs={'group_name': A('playlist_name')},
        text='Revisit',
        verbose_name='View',
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
    playlist_pass_bool = tables.columns.Column(
        verbose_name='Pass',
        # is conditional formatting possible?
        orderable=False,
    )
    playlist_pass_date = tables.columns.Column(
        verbose_name='Date all exercises passed',
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
                                     text='View', verbose_name='View', orderable=False)

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

    def render_edit(self, record):
        if not record.has_been_performed:
            return 'Edit'
        return '--'

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
    view = tables.columns.LinkColumn('lab:exercise-groups',
                                     kwargs={'group_name': A('name')},
                                     text='View', verbose_name='View', orderable=False)

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

    def render_edit(self, record):
        if not record.has_been_performed:
            return 'Edit'
        return '--'

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
                                     text='View', verbose_name='View', orderable=False)

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

    def render_edit(self, record):
        # if record.has_been_performed:
            # return '--'
        return 'Edit'

    def render_delete(self, record):
        if not record.has_been_performed:
            return 'Delete'
        return ''

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        order_by = ('-id')
        template_name = "django_tables2/bootstrap4.html"
