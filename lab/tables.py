from django_tables2 import tables, A

from apps.exercises.models import Playlist


class CoursePageTable(tables.Table):
    name = tables.columns.LinkColumn(
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
        viewname='lab:exercise-groups',
        kwargs={'group_name': A('name')},
        verbose_name='Name of Playlist'
    )

    class Meta:
        model = Playlist
        attrs = {"class": "paleblue"}
        fields = ('name', 'id', 'authored_by')
