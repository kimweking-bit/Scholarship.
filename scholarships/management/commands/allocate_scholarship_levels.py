from __future__ import annotations

import random

from django.core.management.base import BaseCommand

from scholarships.categorization import infer_level_for_scholarship
from scholarships.models import Scholarship


class Command(BaseCommand):
    help = "Assign Scholarship.level values (Degree/Masters/PhD/Diploma/etc.) to existing records."

    def add_arguments(self, parser):
        parser.add_argument("--degree-ratio", type=float, default=0.55, help="Default: 0.55")
        parser.add_argument("--masters-ratio", type=float, default=0.25, help="Default: 0.25")
        parser.add_argument("--phd-ratio", type=float, default=0.12, help="Default: 0.12")
        parser.add_argument("--diploma-ratio", type=float, default=0.08, help="Default: 0.08")
        parser.add_argument(
            "--seed",
            type=int,
            default=20260317,
            help="PRNG seed used to shuffle scholarships before assignment. Default: 20260317",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing levels (default: only fill empty levels).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        degree_ratio = float(options["degree_ratio"])
        masters_ratio = float(options["masters_ratio"])
        phd_ratio = float(options["phd_ratio"])
        diploma_ratio = float(options["diploma_ratio"])
        seed = int(options["seed"])
        force = bool(options["force"])
        dry_run = bool(options["dry_run"])

        for r in [degree_ratio, masters_ratio, phd_ratio, diploma_ratio]:
            if r < 0 or r > 1:
                raise SystemExit("ratios must be between 0 and 1")
        total_ratio = degree_ratio + masters_ratio + phd_ratio + diploma_ratio
        if total_ratio > 1.0 + 1e-9:
            raise SystemExit("sum of ratios must be <= 1.0")

        qs = Scholarship.objects.all().only("id", "title", "description", "requirements", "level").order_by("id")
        if not force:
            qs = qs.filter(level="")

        scholarships = list(qs)
        total = len(scholarships)
        if total == 0:
            self.stdout.write("No scholarships to update.")
            return

        rng = random.Random(seed)
        rng.shuffle(scholarships)

        degree_count = int(total * degree_ratio + 0.5)
        masters_count = int(total * masters_ratio + 0.5)
        phd_count = int(total * phd_ratio + 0.5)
        diploma_count = int(total * diploma_ratio + 0.5)

        # Ensure we don't over-allocate due to rounding.
        planned = [degree_count, masters_count, phd_count, diploma_count]
        if sum(planned) > total:
            overflow = sum(planned) - total
            # Reduce from the largest buckets first.
            for _ in range(overflow):
                i = max(range(len(planned)), key=lambda j: planned[j])
                planned[i] = max(0, planned[i] - 1)
            degree_count, masters_count, phd_count, diploma_count = planned

        buckets = (
            ([Scholarship.LEVEL_UNDERGRADUATE] * degree_count)
            + ([Scholarship.LEVEL_MASTERS] * masters_count)
            + ([Scholarship.LEVEL_PHD] * phd_count)
            + ([Scholarship.LEVEL_DIPLOMA] * diploma_count)
        )
        while len(buckets) < total:
            buckets.append(Scholarship.LEVEL_OTHER)
        rng.shuffle(buckets)

        to_update: list[Scholarship] = []
        for s, planned_level in zip(scholarships, buckets, strict=False):
            inferred = infer_level_for_scholarship(
                title=s.title, description=getattr(s, "description", ""), requirements=getattr(s, "requirements", "")
            )
            new_level = inferred or planned_level
            if s.level != new_level:
                s.level = new_level
                to_update.append(s)

        if dry_run:
            self.stdout.write(f"dry-run: total={total} would_update={len(to_update)} force={force}")
            for s in to_update[:25]:
                self.stdout.write(f"  {s.id}: {s.title} -> {s.level}")
            if len(to_update) > 25:
                self.stdout.write(f"  ... and {len(to_update) - 25} more")
            return

        if to_update:
            Scholarship.objects.bulk_update(to_update, ["level"], batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"Done. total={total} updated={len(to_update)} force={force}"))

