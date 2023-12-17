from import_export import resources
from import_export.fields import Field
from import_export.results import RowResult

from apps.exercises.models import Exercise, Playlist, Course


class BaseContentResource(resources.ModelResource):
    authored_by = Field(attribute="authored_by__email", column_name="authored_by")

    class Meta:
        widgets = {
            "created": {"format": "%Y.%m.%d"},
            "updated": {"format": "%Y.%m.%d"},
        }
        clean_model_instances = True
        sample_file_fields = ()

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.is_sample = kwargs.pop("is_sample", False)
        super(BaseContentResource, self).__init__(*args, **kwargs)

    def import_field(self, field, obj, data, is_m2m=False, **kwargs):
        obj.authored_by = self.request.user
        return super(BaseContentResource, self).import_field(
            field, obj, data, is_m2m, **kwargs
        )

    def import_row(self, row, instance_loader, **kwargs):
        import_result = super(BaseContentResource, self).import_row(
            row, instance_loader, **kwargs
        )
        if import_result.import_type in RowResult.IMPORT_TYPE_INVALID:
            # import_result.diff = [row[val] for val in row]
            # import_result.diff.append('Errors: {}'.format(import_result.validation_error.message_dict))
            import_result.errors = [import_result.validation_error.message_dict]
        return import_result

    def get_export_fields(self):
        export_fields = super(BaseContentResource, self).get_export_fields()
        if self.is_sample:
            export_fields = [
                field
                for field in export_fields
                if field.attribute in self._meta.sample_import_file_fields
            ]
        return export_fields


class ExerciseResource(BaseContentResource):
    class Meta(BaseContentResource.Meta):
        model = Exercise
        fields = (
            "id",
            "description",
            "data",
            "rhythm",
            "time_signature",
            "is_public",
            "authored_by",
            "locked",
            "created",
            "updated",
        )
        export_order = fields
        sample_import_file_fields = (
            "description",
            "data",
            "rhythm",
            "time_signature",
            "is_public",
            # "locked",
        )


class PlaylistResource(BaseContentResource):
    class Meta(BaseContentResource.Meta):
        model = Playlist
        fields = (
            "id",
            "name",
            "exercises",
            "transpose_requests",
            "transposition_type",
            "is_public",
            "is_auto",
            "authored_by",
            "created",
            "updated",
        )
        export_order = fields
        sample_import_file_fields = (
            "name",
            "exercises",
            "transpose_requests",
            "transposition_type",
            "is_public",
        )


class CourseResource(BaseContentResource):
    class Meta(BaseContentResource.Meta):
        model = Course
        fields = (
            "id",
            "title",
            "playlists",
            "is_public",
            "authored_by",
            "created",
            "updated",
        )
        export_order = fields
        sample_import_file_fields = ("title", "playlists", "is_public")
