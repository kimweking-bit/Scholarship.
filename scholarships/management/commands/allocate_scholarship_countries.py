from __future__ import annotations

import random

from django.core.management.base import BaseCommand

from scholarships.models import Scholarship


DEFAULT_OTHER_COUNTRIES = [
    "Uganda",
    "Tanzania",
    "Rwanda",
    "Ethiopia",
    "Nigeria",
    "Ghana",
    "South Africa",
    "Egypt",
    "United States",
    "Canada",
    "United Kingdom",
    "Germany",
    "France",
    "Netherlands",
    "Sweden",
    "India",
    "Australia",
]


class Command(BaseCommand):
    help = "Assign Scholarship.country values with a target share in Kenya (default: 75%)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kenya-ratio",
            type=float,
            default=0.75,
            help="Fraction of scholarships that should be assigned to Kenya (0..1). Default: 0.75",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260317,
            help="PRNG seed used to shuffle scholarships before assignment. Default: 20260317",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        kenya_ratio = float(options["kenya_ratio"])
        seed = int(options["seed"])
        dry_run = bool(options["dry_run"])

        if not (0.0 <= kenya_ratio <= 1.0):
            raise SystemExit("--kenya-ratio must be between 0 and 1")

        qs = Scholarship.objects.all().only("id", "country").order_by("id")
        scholarships = list(qs)
        total = len(scholarships)
        if total == 0:
            self.stdout.write("No scholarships found.")
            return

        rng = random.Random(seed)
        rng.shuffle(scholarships)

        kenya_count = int(total * kenya_ratio + 0.5)  # round to nearest
        kenya_count = max(0, min(total, kenya_count))

        other_countries = list(DEFAULT_OTHER_COUNTRIES)
        rng.shuffle(other_countries)
        if "Kenya" in other_countries:
            other_countries = [c for c in other_countries if c != "Kenya"]
        if not other_countries:
            raise SystemExit("No non-Kenya countries available.")

        to_update: list[Scholarship] = []

        for idx, s in enumerate(scholarships):
            if idx < kenya_count:
                new_country = "Kenya"
            else:
                new_country = other_countries[(idx - kenya_count) % len(other_countries)]

            if s.country != new_country:
                s.country = new_country
                to_update.append(s)

        if dry_run:
            self.stdout.write(f"dry-run: total={total} kenya_target={kenya_count} would_update={len(to_update)}")
            for s in to_update[:25]:
                self.stdout.write(f"  {s.id}: {s.country}")
            if len(to_update) > 25:
                self.stdout.write(f"  ... and {len(to_update) - 25} more")
            return

        if to_update:
            Scholarship.objects.bulk_update(to_update, ["country"], batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"Done. total={total} kenya={kenya_count} updated={len(to_update)}"))

