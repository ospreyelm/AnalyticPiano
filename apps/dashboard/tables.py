from django.contrib.auth import get_user_model
from django_tables2 import tables, A

User = get_user_model()


class SupervisorsTable(tables.Table):
    supervisor = tables.columns.Column(
        attrs={"td": {"bgcolor": "white", "width": "250px"}},
        verbose_name='Supervisors'
    )

    # remove = tables.columns.LinkColumn('dashboard:unsubscribe',
    #                                    kwargs={'supervisor_id': A('supervisor.id')},
    #                                    text='remove', verbose_name='', orderable=False)

    class Meta:
        attrs = {'class': 'paleblue'}
        template_name = "django_tables2/bootstrap4.html"


class SubscribersTable(tables.Table):
    subscriber = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                           kwargs={'subscriber_id': A('subscriber.id')},
                                           attrs={"td": {"bgcolor": "white", "width": "250px"}},
                                           verbose_name='Subscribers')
    remove = tables.columns.LinkColumn('dashboard:remove-subscriber',
                                       kwargs={'subscriber_id': A('subscriber.id')},
                                       text='remove', verbose_name='', orderable=False)

    class Meta:
        attrs = {'class': 'paleblue'}
        template_name = "django_tables2/bootstrap4.html"


class PerformancesListTable(tables.Table):
    playlist = tables.columns.LinkColumn('dashboard:subscriber-playlist-performance',
                                         kwargs={'playlist_id': A('playlist.id'),
                                                 'subscriber_id': A('user.id')},
                                         attrs={"td": {"bgcolor": "white", "width": "250px"}},
                                         verbose_name='Playlist')
    created = tables.columns.DateTimeColumn(verbose_name='Performed At')
    user = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                     kwargs={'subscriber_id': A('user.id')},
                                     attrs={"td": {"bgcolor": "white", "width": "250px"}},
                                     verbose_name='Performed By')

    class Meta:
        attrs = {'class': 'paleblue'}
        template_name = "django_tables2/bootstrap4.html"


class SubscriberPlaylistPerformanceTable(tables.Table):
    playlist_id = tables.columns.Column()
    # performed_at = tables.columns.DateTimeColumn(verbose_name='Performed At')
    exercise_count = tables.columns.Column(verbose_name='Total exercises performed')
    performer = tables.columns.LinkColumn('dashboard:subscriber-performances',
                                          kwargs={'subscriber_id': A('subscriber_id')},
                                          attrs={"td": {"bgcolor": "white", "width": "250px"}},
                                          verbose_name='Performed By')

    class Meta:
        attrs = {'class': 'paleblue'}
        template_name = "django_tables2/bootstrap4.html"
        order_by = ('-exercise_count', 'email')
        sequence = ('playlist_id', '...', 'exercise_count', 'performer')
