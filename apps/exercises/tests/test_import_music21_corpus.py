import json
import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class ImportMusic21CorpusTests(TestCase):
    @patch("apps.exercises.management.commands.import_music21_corpus.corpus")
    @patch("apps.exercises.management.commands.import_music21_corpus.converter")
    def test_dry_run_reports_without_writing(self, mock_converter, mock_corpus):
        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_result.sourcePath = "bach/bwv1.6.mxl"
        mock_corpus.search.return_value = [mock_result]
        mock_score = object()
        mock_corpus.parse.return_value = mock_score
        mock_converter.score_to_cir.return_value = {"meta": {"key": "C", "time": "4/4"}, "measures": []}

        out = StringIO()
        call_command("import_music21_corpus", riemenschneider="1-1", output_dir="data/corpus/bach", dry_run=True, stdout=out)

        self.assertIn("dry-run", out.getvalue().lower())

    @patch("apps.exercises.management.commands.import_music21_corpus.corpus")
    @patch("apps.exercises.management.commands.import_music21_corpus.converter")
    def test_idempotent_skips_existing_file(self, mock_converter, mock_corpus):
        target = os.path.join("data", "corpus", "bach", "bwv1.6.json")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as f:
            json.dump({"score": {"meta": {"key": "C", "time": "4/4"}, "measures": []}}, f)
        self.addCleanup(lambda: os.path.exists(target) and os.remove(target))

        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_result.sourcePath = "bach/bwv1.6.mxl"
        mock_corpus.search.return_value = [mock_result]

        out = StringIO()
        call_command("import_music21_corpus", riemenschneider="1-1", output_dir="data/corpus/bach", stdout=out)

        self.assertIn("skipped", out.getvalue().lower())
