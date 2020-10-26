from django.contrib.auth import get_user_model
from django_tables2 import tables, A

User = get_user_model()


class SupervisorsTable(tables.Table):
    name = tables.columns.Column(
        accessor=A('supervisor.get_full_name'),
        attrs={"td": {"bgcolor": "white", "width": "250px"}},
        verbose_name='Supervisor Name'
    )
    supervisor = tables.columns.Column(
        attrs={"td": {"bgcolor": "white", "width": "250px"}},
        verbose_name='Supervisor Email'
    )

    # remove = tables.columns.LinkColumn('dashboard:unsubscribe',
    #                                    kwargs={'supervisor_id': A('supervisor.id')},
    #                                    text='remove', verbose_name='', orderable=False)

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class SubscribersTable(tables.Table):
    name = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                     kwargs={'subscriber_id': A('subscriber.id')},
                                     accessor=A('subscriber.get_full_name'),
                                     attrs={"td": {"bgcolor": "white", "width": "250px"}},
                                     verbose_name='Subscriber Name')
    subscriber = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                           kwargs={'subscriber_id': A('subscriber.id')},
                                           attrs={"td": {"bgcolor": "white", "width": "250px"}},
                                           verbose_name='Subscriber Email')
    remove = tables.columns.LinkColumn('dashboard:remove-subscriber',
                                       kwargs={'subscriber_id': A('subscriber.id')},
                                       text='remove', verbose_name='', orderable=False)

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"


class PerformancesListTable(tables.Table):
    playlist = tables.columns.LinkColumn(
      'dashboard:subscriber-playlist-performance',
      verbose_name='Playlist (sorts by ID)',
      kwargs={
        'playlist_id': A('playlist.id'),
        'subscriber_id': A('user.id')
      },
      attrs={
        "td": {"bgcolor": "white", "width": "auto"}
      }
    )
    created = tables.columns.DateColumn(
      verbose_name='Date of first practice',
      format='Y-m-d • l, F j',
      attrs={
        "td": {"bgcolor": "white", "width": "auto"}
      }
    )
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
    email = tables.columns.LinkColumn(
      'dashboard:subscriber-performances',
      verbose_name='Performer Email',
      kwargs={
        'subscriber_id': A('user.id')
      },
      accessor=A('user.email'),
      attrs={
        "td": {"bgcolor": "white", "width": "auto"}
      }
    )

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        order_by = ('-created')
        template_name = "django_tables2/bootstrap4.html"


class SubscriberPlaylistPerformanceTable(tables.Table):
    playlist_name = tables.columns.LinkColumn(
      attrs={"td": {"bgcolor": "white", "width": "auto"}},
      viewname='lab:exercise-groups',
      kwargs={'group_name': A('playlist_name')},
    )

    # performed_at = tables.columns.DateTimeColumn(verbose_name='Performed At')
    exercise_count = tables.columns.Column(
      verbose_name='Exercise tally',
      attrs={"td": {"bgcolor": "white", "width": "auto"}}
    )
    performer_name = tables.columns.LinkColumn(
      'dashboard:subscriber-performances',
      kwargs={'subscriber_id': A('subscriber_id')},
      accessor=A('perfomer_obj.get_full_name'),
      attrs={"td": {"bgcolor": "white", "width": "auto"}},
      verbose_name='Performer Name'
    )
    performer = tables.columns.LinkColumn(
      'dashboard:subscriber-performances',
      kwargs={'subscriber_id': A('subscriber_id')},
      attrs={"td": {"bgcolor": "white", "width": "auto"}},
      verbose_name='Performer Email'
    )

    class Meta:
        attrs = {'class': 'paleblue'}
        table_pagination = False
        template_name = "django_tables2/bootstrap4.html"
        order_by = ('-exercise_count', 'email')
        sequence = ('playlist_name', 'exercise_count', '...', 'performer_name', 'performer')
