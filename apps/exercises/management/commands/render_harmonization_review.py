from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.exercises.harmonization.figures import derive_required_notes


CASES = [
    ("C", "C", "6"),
    ("C", "F", "6"),
    ("C", "F", "#"),
    ("C", "G", "7"),
    ("G", "F#", "6/5"),
    ("C", "C", "9/7/5/3"),
]


class Command(BaseCommand):
    help = "Render musician-review artifacts for harmonization theory behavior."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="lab/static/harmonization-review.html",
            help="Path to write the review HTML artifact.",
        )

    def handle(self, *args, **options):
        output = Path(options["output"])
        rows = []
        for key_name, bass, figure in CASES:
            derived = derive_required_notes(key_name=key_name, bass_name=bass, figure=figure)
            label = f"{bass} + {figure}"
            rows.append(
                "<tr>"
                f"<td>{key_name}</td>"
                f"<td>{label}</td>"
                f"<td>{'/'.join(derived['expanded_figures'])}</td>"
                f"<td>{', '.join(derived['required_note_names'])}</td>"
                f"<td>{', '.join(str(pc) for pc in derived['required_upper_pcs'])}</td>"
                "</tr>"
            )

        html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Harmonization Review</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; color: #172033; }
    table { border-collapse: collapse; width: 100%; max-width: 900px; }
    th, td { border: 1px solid #d8dee9; padding: 8px 10px; text-align: left; }
    th { background: #f5f7fb; }
  </style>
</head>
<body>
  <h1>Figure Parser Review</h1>
  <p>Review whether bass+figure inputs expand to the notes a musician expects.</p>
  <table>
    <thead><tr><th>Key</th><th>Input</th><th>Expanded</th><th>Notes</th><th>Pitch classes</th></tr></thead>
    <tbody>
""" + "\n".join(rows) + """
    </tbody>
  </table>
</body>
</html>
"""
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html)
        self.stdout.write(self.style.SUCCESS(f"Wrote {output}"))
