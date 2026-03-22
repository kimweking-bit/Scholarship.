from __future__ import annotations

import random
from datetime import date

from django.core.management.base import BaseCommand

from scholarships.categorization import infer_category_for_scholarship
from scholarships.management.commands.allocate_scholarship_countries import DEFAULT_OTHER_COUNTRIES
from scholarships.models import Scholarship


SEED = [
    {
        "title": "Mastercard Foundation Scholarship",
        "organization": "Mastercard Foundation",
        "amount_display": "Full Scholarship",
        "deadline": "2026-08-30",
        "requirements": "\n".join(
            [
                "Must be from Africa",
                "Strong academic performance",
                "Leadership potential",
            ]
        ),
        "description": (
            "Provides full funding for undergraduate and postgraduate studies including tuition, "
            "accommodation, and living expenses."
        ),
    },
    {
        "title": "Kenya Government University Scholarship",
        "organization": "Government of Kenya",
        "amount_display": "KES 150,000 per year",
        "deadline": "2026-07-15",
        "requirements": "\n".join(
            [
                "Kenyan citizen",
                "Accepted into a university",
                "Financial need",
            ]
        ),
        "description": "Supports Kenyan students pursuing university education.",
    },
    {
        "title": "Google Tech Scholarship",
        "organization": "Google",
        "amount_display": "$10,000",
        "deadline": "2026-09-10",
        "requirements": "\n".join(
            [
                "Computer science student",
                "Good academic record",
                "Passion for technology",
            ]
        ),
        "description": "Supports students pursuing careers in technology.",
    },
    {
        "title": "Global Development Scholarship",
        "organization": "United Nations",
        "amount_display": "$8,000",
        "deadline": "2026-10-01",
        "requirements": "\n".join(
            [
                "International students",
                "Interest in global development",
            ]
        ),
        "description": "Supports students studying international relations and development.",
    },
    {
        "title": "African Leadership Scholarship",
        "organization": "African Union",
        "amount_display": "Full Scholarship",
        "deadline": "2026-08-01",
        "requirements": "\n".join(
            [
                "African student",
                "Leadership experience",
            ]
        ),
        "description": "Develops future African leaders through fully funded education.",
    },
]


class Command(BaseCommand):
    help = "Seed the database with example Scholarship records."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        rng = random.Random(20260317)

        for row in SEED:
            defaults = dict(row)
            title = defaults.pop("title")

            deadline = defaults.get("deadline")
            if isinstance(deadline, str) and deadline:
                defaults["deadline"] = date.fromisoformat(deadline)

            defaults.setdefault(
                "category",
                infer_category_for_scholarship(title=title, organization=defaults.get("organization", "")) or "",
            )

            defaults.setdefault(
                "country",
                "Kenya" if rng.random() < 0.75 else rng.choice(DEFAULT_OTHER_COUNTRIES),
            )

            obj, created = Scholarship.objects.update_or_create(title=title, defaults=defaults)
            created_count += int(created)
            updated_count += int(not created)

            self.stdout.write(f"{'CREATED' if created else 'UPDATED'}: {obj.title}")

        self.stdout.write(self.style.SUCCESS(f"Done. created={created_count} updated={updated_count}"))
