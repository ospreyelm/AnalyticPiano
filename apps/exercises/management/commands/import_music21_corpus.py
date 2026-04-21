import json
import os
import re

from django.core.management.base import BaseCommand, CommandError
from music21 import corpus

from apps.exercises.utils import music21_builder as converter


BWV_RE = re.compile(r"bwv\d+\.\d+", re.IGNORECASE)


def _parse_range(text):
    if "-" not in text:
        n = int(text)
        return n, n
    start, end = text.split("-", 1)
    return int(start), int(end)


class Command(BaseCommand):
    help = "Import Riemenschneider Bach chorales from music21 corpus to local CIR JSON"

    def add_arguments(self, parser):
        parser.add_argument("--riemenschneider", default="1-371")
        parser.add_argument("--output-dir", default=os.path.join("data", "corpus", "bach"))
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        # ...
        start, end = _parse_range(options["riemenschneider"])
        output_dir = options["output_dir"]
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]

        if not dry_run:
            os.makedirs(output_dir, exist_ok=True)

        results = corpus.search("bach", "composer")
        if not results:
            raise CommandError("No Bach chorales returned by music21 corpus search")

        written = 0
        skipped = 0
        failed = 0

        for r in results:
            path = str(r.sourcePath)
            m = BWV_RE.search(path)
            if not m:
                continue
            bwv_id = m.group(0).lower()

            filename = f"{bwv_id}.json"
            out_path = os.path.join(output_dir, filename)

            if os.path.exists(out_path) and not overwrite:
                skipped += 1
                continue

            try:
                score = r.parse()
                cir = converter.score_to_cir(score)
                payload = {
                    "source": {"path": path, "bwv": bwv_id},
                    "score": cir,
                    "events": [],
                    "tags": [],
                }
                if not dry_run:
                    with open(out_path, "w") as f:
                        json.dump(payload, f)
                written += 1
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.WARNING(f"Failed {path}: {exc}"))

        mode = "DRY-RUN" if dry_run else "WRITE"
        self.stdout.write(f"{mode} complete. written={written} skipped={skipped} failed={failed}")
