from django.db import models
from django.db.models import When, Case
from apps.accounts.admin import User
from django_tables2 import tables, A
from django.db.models import Q

from apps.exercises.models import Playlist, PlaylistCourseOrdered


class CoursePageTable(tables.Table):
    order = tables.columns.Column(verbose_name="Unit #", orderable=True)
    name = tables.columns.LinkColumn(
        # attrs={"td": {"bgcolor": "white", "width": "auto"}},
        viewname="lab:playlist-view",
        kwargs={"playlist_id": A("id")},
        verbose_name="Playlist Name",
    )
    publish_date = tables.columns.DateColumn(
        verbose_name="Publish Date",
        format="Y_m_d",
        orderable=True,
    )
    due_date = tables.columns.DateColumn(
        verbose_name="Due Date",
        format="Y_m_d",
        orderable=True,
    )
    id = tables.columns.Column(verbose_name="ID", orderable=True)
    authored_by_id = tables.columns.Column(
        verbose_name="Author",
        orderable=True,
    )

    class Meta:
        attrs = {"class": "paleblue"}
        order_by = "order"

    def __init__(self, *args, **kwargs):
        self.course = kwargs.pop("course")
        super(CoursePageTable, self).__init__(*args, **kwargs)

    def render_authored_by_id(self, record):
        return User.objects.get(id=record["authored_by_id"]).email

    def order_publish_date(self, queryset, is_descending):
        return self._order_by_date(
            queryset, is_descending, self.course.publish_dates_dict
        )

    def order_due_date(self, queryset, is_descending):
        return self._order_by_date(queryset, is_descending, self.course.due_dates_dict)

    def _order_by_date(self, queryset, is_descending, dates_dict):
        sorted_dict = {
            k: v
            for k, v in sorted(
                dates_dict.items(), key=lambda item: item[1], reverse=is_descending
            )
        }
        playlists = [k for k, v in sorted_dict.items()]

        whens = []
        for sort_index, value in enumerate(playlists):
            whens.append(When(id=value, then=sort_index))

        playlists = queryset.annotate(
            _sort_index=Case(*whens, output_field=models.CharField())
        ).order_by("_sort_index")

        return (playlists, True)
