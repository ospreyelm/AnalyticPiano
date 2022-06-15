from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView
from django.views.generic.base import View
from django_extensions.management.color import no_style
from tablib import Dataset

from apps.dashboard.forms import ContentImportForm
from apps.exercises.models import Exercise, Playlist, Course
from apps.exercises.resources import ExerciseResource, PlaylistResource, CourseResource


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class BaseExportView(View):
    resource_class = None
    model = None
    filename_prefix = None

    def get(self, *args, **kwargs):
        assert self.resource_class is not None
        assert self.model is not None
        assert self.filename_prefix is not None

        is_sample_file = self.request.GET.get('sample')
        if is_sample_file:
            objs = self.model.objects.none()
            dataset = self.resource_class(is_sample=True).export(objs)
        else:
            objs = self.model.objects.filter(authored_by=self.request.user)
            dataset = self.resource_class().export(objs)
        response = HttpResponse(dataset.csv, content_type='text/csv')
        filename = f'{self.filename_prefix}_{timezone.now().date() if not is_sample_file else "import_sample"}'
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        return response


class ExerciseExportView(BaseExportView):
    resource_class = ExerciseResource
    model = Exercise
    filename_prefix = 'exercises'


class PlaylistExportView(BaseExportView):
    resource_class = PlaylistResource
    model = Playlist
    filename_prefix = 'playlists'


class CourseExportView(BaseExportView):
    resource_class = CourseResource
    model = Course
    filename_prefix = 'courses'


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class BaseImportView(FormView):
    form_class = ContentImportForm
    template_name = 'dashboard/import.html'
    success_url_param = '?import_success=True'
    resource_class = None
    model = None

    def form_valid(self, form):
        resource = self.resource_class(request=self.request)
        dataset = Dataset()
        new_content = self.request.FILES['file']
        data = dataset.load(new_content.read().decode(), format='csv', headers=True)
        result = resource.import_data(data, dry_run=True)

        sequence_sql = connection.ops.sequence_reset_sql(no_style(), [self.model])
        with connection.cursor() as cursor:
            for sql in sequence_sql:
                cursor.execute(sql)

        if result.has_errors():
            errors = [f'Row {error[0] + 1}: {error[1][0].error if hasattr(error[1][0], "error") else error[1][0]}'
                      for error in result.row_errors()]
            form.add_error('file', errors)
            return render_to_response('dashboard/import.html', {'form': form})

        resource.import_data(data, dry_run=False, raise_errors=True)
        messages.success(self.request, f'{result.totals["new"]} new row(s) have been successfully imported.')
        return HttpResponseRedirect(self.get_success_url())


class ExerciseImportView(BaseImportView):
    resource_class = ExerciseResource
    model = Exercise

    def get_success_url(self):
        return reverse('dashboard:exercises-list') + self.success_url_param

    def get_context_data(self, **kwargs):
        context = super(ExerciseImportView, self).get_context_data(**kwargs)
        context['sample_file_url'] = reverse('dashboard:export-exercises') + '?sample=True'
        return context


class PlaylistImportView(BaseImportView):
    resource_class = PlaylistResource
    model = Playlist

    def get_success_url(self):
        return reverse('dashboard:playlists-list') + self.success_url_param

    def get_context_data(self, **kwargs):
        context = super(PlaylistImportView, self).get_context_data(**kwargs)
        context['sample_file_url'] = reverse('dashboard:export-playlists') + '?sample=True'
        return context


class CourseImportView(BaseImportView):
    resource_class = CourseResource
    model = Course

    def get_success_url(self):
        return reverse('dashboard:courses-list') + self.success_url_param

    def get_context_data(self, **kwargs):
        context = super(CourseImportView, self).get_context_data(**kwargs)
        context['sample_file_url'] = reverse('dashboard:export-courses') + '?sample=True'
        return context
