from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.exercises.models import truncate_timestamps


class TimestampTruncationTests(TestCase):
    @patch("apps.exercises.models.connections")
    def test_truncate_timestamps_parameterizes_string_primary_keys(self, mock_connections):
        connection = MagicMock()
        cursor_manager = MagicMock()
        cursor = MagicMock()
        cursor_manager.__enter__.return_value = cursor
        connection.cursor.return_value = cursor_manager
        connection.ops.quote_name.side_effect = lambda value: f'"{value}"'
        mock_connections.__getitem__.return_value = connection

        instance = MagicMock()
        instance._meta.db_table = "exercises_exercise"
        instance._meta.pk.name = "id"
        instance.pk = "EA01AO"

        truncate_timestamps(sender=None, instance=instance)

        cursor.execute.assert_called_once_with(
            'UPDATE "exercises_exercise" '
            "SET created = DATE_TRUNC('second', created), updated = DATE_TRUNC('second', updated) "
            'WHERE "id" = %s',
            ["EA01AO"],
        )
