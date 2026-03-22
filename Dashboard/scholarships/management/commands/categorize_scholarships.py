from __future__ import annotations

from django.core.management.base import BaseCommand

from scholarships.categorization import infer_category_for_scholarship
from scholarships.models import Scholarship


class Command(BaseCommand):
    help = "Auto-fill Scholarship.category for records that are missing it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing categories (default: only fill empty categories).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        force: bool = bool(options["force"])
        dry_run: bool = bool(options["dry_run"])

        qs = Scholarship.objects.all().only("id", "title", "organization", "category")
        if not force:
            qs = qs.filter(category="")

        to_update: list[Scholarship] = []
        skipped = 0

        for s in qs.iterator(chunk_size=500):
            inferred = infer_category_for_scholarship(title=s.title, organization=s.organization)
            if not inferred:
                skipped += 1
                continue
            if not force and s.category:
                skipped += 1
                continue

            s.category = inferred
            to_update.append(s)

        if dry_run:
            self.stdout.write(f"dry-run: would_update={len(to_update)} skipped={skipped}")
            for s in to_update[:20]:
                self.stdout.write(f"  {s.id}: {s.title} -> {s.category}")
            if len(to_update) > 20:
                self.stdout.write(f"  ... and {len(to_update) - 20} more")
            return

        if to_update:
            Scholarship.objects.bulk_update(to_update, ["category"], batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"Done. updated={len(to_update)} skipped={skipped} force={force}"))

