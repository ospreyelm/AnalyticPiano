import django_filters

from apps.exercises.models import Course


class CourseGroupsFilter(django_filters.FilterSet):
    groups = django_filters.ModelMultipleChoiceFilter()

    class Meta:
        model = Course
        fields = ['groups']


class CourseActivityGroupsFilter(django_filters.FilterSet):
    groups = django_filters.MultipleChoiceFilter(label='Groups')

    def __init__(self, *args, **kwargs):
        super(CourseActivityGroupsFilter, self).__init__(*args, **kwargs)
        group_choices = [[group.id, group.name] for group in kwargs.get('queryset', [])]
        self.form.fields['groups'].choices = group_choices
