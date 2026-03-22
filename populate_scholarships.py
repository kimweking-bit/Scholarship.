import os
import random
from datetime import date, timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from scholarships.management.commands.allocate_scholarship_countries import (  # noqa: E402
    DEFAULT_OTHER_COUNTRIES,
)
from scholarships.models import Scholarship  # noqa: E402
from scholarships.categorization import infer_category_for_scholarship  # noqa: E402

# Clear existing scholarships if needed:
# Scholarship.objects.all().delete()

organizations = [
    "Mastercard Foundation",
    "United Nations",
    "Google",
    "African Union",
    "Kenya Government",
    "Microsoft",
    "Facebook",
    "Harvard University",
    "MIT",
    "Oxford University",
    "World Bank",
    "Bill & Melinda Gates Foundation",
    "UNICEF",
    "Commonwealth Scholarship Commission",
]

titles = [
    "Global Development Scholarship",
    "African Leadership Scholarship",
    "Tech Innovators Scholarship",
    "Women in STEM Scholarship",
    "Future Leaders Scholarship",
    "International Excellence Scholarship",
    "Community Impact Scholarship",
    "Education for All Scholarship",
    "Young Achievers Scholarship",
    "Next Gen Leaders Scholarship",
]

amounts = [
    "Full Scholarship",
    "$10,000",
    "$8,000",
    "$12,000",
    "KES 150,000 per year",
    "$5,000",
    "Full Tuition",
    "Partial Funding",
]

COUNT = 80

for i in range(1, COUNT + 1):
    title = f"{random.choice(titles)} #{i}"
    org = random.choice(organizations)
    amount_display = random.choice(amounts)
    deadline = date.today() + timedelta(days=random.randint(30, 365))
    requirements = "Strong academic record, leadership potential, and motivation to succeed."
    description = f"{title} offered by {org}. Covers tuition and living expenses."
    category = infer_category_for_scholarship(title=title, organization=org) or ""
    country = "Kenya" if random.random() < 0.75 else random.choice(DEFAULT_OTHER_COUNTRIES)

    Scholarship.objects.create(
        title=title,
        organization=org,
        country=country,
        category=category,
        amount_display=amount_display,
        deadline=deadline,
        requirements=requirements,
        description=description,
    )

print(f"Created {COUNT} scholarships.")
