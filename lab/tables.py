from django_tables2 import tables, A

from apps.exercises.models import Playlist


class CoursePageTable(tables.Table):
    name = tables.columns.LinkColumn(
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
        viewname='lab:playlist-view',
        kwargs={'playlist_name': A('name')},
        verbose_name='Unit'
    )
    publish_date = tables.columns.DateColumn(
        verbose_name='Publish Date',
        format='Y_m_d',
        orderable=False,
    )
    due_date = tables.columns.DateColumn(
        verbose_name='Due Date',
        format='Y_m_d',
        orderable=False,
    )

    # num = tables.columns.Column(
    #     verbose_name='#',
    #     # index of this playlist in course.playlists
    # )

    class Meta:
        model = Playlist
        attrs = {"class": "paleblue"}
        fields = ('name', 'id', 'authored_by', 'publish_date', 'due_date')

    def __init__(self, *args, **kwargs):
        self.course = kwargs.pop('course')
        super(CoursePageTable, self).__init__(*args, **kwargs)

    def render_publish_date(self, record):
        return self.course.publish_dates_dict.get(record.id)

    def render_due_date(self, record):
        return self.course.due_dates_dict.get(record.id)
