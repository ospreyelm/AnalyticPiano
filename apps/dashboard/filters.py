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
        min_unit_num = cleaned_data["min_unit_num"]
        max_unit_num = cleaned_data["max_unit_num"]
        # if (min_unit_num != None and min_unit_num <= 0) or (
        #     max_unit_num != None and max_unit_num <= 0
        # ):
        #     raise ValidationError("Order boundaries must be 1 or greater")
        # if min_unit_num and max_unit_num and min_unit_num > max_unit_num:
        #     raise ValidationError("Invalid range")

        return cleaned_data


class CourseActivityOrderFilter(django_filters.FilterSet):
    min_unit_num = django_filters.NumberFilter(label="From Unit #", label_suffix=" ")
    max_unit_num = django_filters.NumberFilter(label="through Unit #", label_suffix=" ")

    def __init__(self, *args, **kwargs):
        super(CourseActivityOrderFilter, self).__init__(*args, **kwargs)

    class Meta:
        form = CourseActivityOrderFilterForm


class ListIDFilter(django_filters.FilterSet):
    min_id = django_filters.CharFilter(
        label="From ID", field_name="id", label_suffix=" "
    )
    max_id = django_filters.CharFilter(
        label="through ID", field_name="id", label_suffix=" "
    )


class PlaylistListNameFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(label="Name contains", label_suffix=" ", lookup_expr="icontains")


class ExerciseListDescriptionFilter(django_filters.FilterSet):
    description = django_filters.CharFilter(lookup_expr="icontains")


class ConnectionCombinedInfoFilter(django_filters.FilterSet):
    combined_info = django_filters.CharFilter(
        label="Search table—name or email contains", label_suffix=" ", lookup_expr="icontains"
    )
