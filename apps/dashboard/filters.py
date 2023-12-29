import django_filters
from django import forms
from apps.exercises.models import Course, Playlist
from django.core.exceptions import ValidationError


class CourseGroupsFilter(django_filters.FilterSet):
    groups = django_filters.ModelMultipleChoiceFilter()

    class Meta:
        model = Course
        fields = ["groups"]


class CourseActivityGroupsFilter(django_filters.FilterSet):
    groups = django_filters.MultipleChoiceFilter(label="Groups")

    def __init__(self, *args, **kwargs):
        super(CourseActivityGroupsFilter, self).__init__(*args, **kwargs)
        group_choices = [[group.id, group.name] for group in kwargs.get("queryset", [])]
        self.form.fields["groups"].choices = group_choices


class CourseActivityOrderFilterForm(forms.Form):
    def clean(self):
        cleaned_data = super(CourseActivityOrderFilterForm, self).clean()
        min_order = cleaned_data["min_order"]
        max_order = cleaned_data["max_order"]
        if (min_order != None and min_order <= 0) or (
            max_order != None and max_order <= 0
        ):
            raise ValidationError("Order boundaries must be 1 or greater")
        if min_order and max_order and min_order > max_order:
            raise ValidationError("Invalid range")

        return cleaned_data


class CourseActivityOrderFilter(django_filters.FilterSet):
    min_order = django_filters.NumberFilter(label="Min Playlist Order")
    max_order = django_filters.NumberFilter(label="Max Playlist Order")

    def __init__(self, *args, **kwargs):
        super(CourseActivityOrderFilter, self).__init__(*args, **kwargs)

    class Meta:
        form = CourseActivityOrderFilterForm


class ListIDFilter(django_filters.FilterSet):
    min_id = django_filters.CharFilter(label="Min ID", field_name="id")
    max_id = django_filters.CharFilter(label="Max ID", field_name="id")


class ExerciseListDescriptionFilter(django_filters.FilterSet):
    description = django_filters.CharFilter(lookup_expr="contains")
