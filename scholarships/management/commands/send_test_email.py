from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from scholarships.models import NewsletterSubscriber
from scholarships.newsletter import send_newsletter_welcome_email


class Command(BaseCommand):
    help = "Send the ScholarHub welcome email to a target address using the current email backend."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Recipient email address.")
        parser.add_argument(
            "--user",
            help="Optional username or email of an existing Django user to attach for dashboard links.",
        )
        parser.add_argument(
            "--source",
            default="manual-test",
            help="Subscriber source label to save on the record. Default: manual-test",
        )

    def handle(self, *args, **options):
        to_email = str(options["to"]).strip().lower()
        if not to_email:
            raise CommandError("--to is required")

        user = None
        user_lookup = (options.get("user") or "").strip()
        if user_lookup:
            User = get_user_model()
            user = User.objects.filter(username=user_lookup).first() or User.objects.filter(email__iexact=user_lookup).first()
            if user is None:
                raise CommandError(f"No Django user found for '{user_lookup}'.")

        subscriber = NewsletterSubscriber.objects.filter(email__iexact=to_email).first()
        if subscriber is None:
            subscriber = NewsletterSubscriber.objects.create(
                email=to_email,
                user=user,
                source=(options.get("source") or "").strip()[:80],
                is_active=True,
            )
            created = True
        else:
            created = False
            update_fields = []
            if user is not None and subscriber.user_id != user.id:
                subscriber.user = user
                update_fields.append("user")
            if not subscriber.is_active:
                subscriber.is_active = True
                update_fields.append("is_active")
            source = (options.get("source") or "").strip()[:80]
            if source and subscriber.source != source:
                subscriber.source = source
                update_fields.append("source")
            if update_fields:
                subscriber.save(update_fields=update_fields + ["updated_at"])

        self.stdout.write(f"Email backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"To: {subscriber.email}")

        try:
            send_newsletter_welcome_email(subscriber)
        except Exception as exc:
            raise CommandError(f"Email send failed: {exc}") from exc

        result = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Welcome email sent successfully ({result} subscriber record)."))
