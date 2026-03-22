from __future__ import annotations

from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Inspect ScholarHub email delivery settings and optionally test the SMTP connection."

    def add_arguments(self, parser):
        parser.add_argument(
            "--connect",
            action="store_true",
            help="Attempt to open and close the configured email connection.",
        )

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND
        self.stdout.write(f"Email backend: {backend}")
        self.stdout.write(f"Default from: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Support email: {settings.SUPPORT_EMAIL}")
        self.stdout.write(f"Site URL: {settings.SITE_URL or '(missing)'}")

        if backend == "django.core.mail.backends.console.EmailBackend":
            self.stdout.write(
                self.style.WARNING(
                    "Console backend is active. Subscribe emails render locally but do not reach real inboxes."
                )
            )
            return

        if backend != "django.core.mail.backends.smtp.EmailBackend":
            self.stdout.write(
                self.style.WARNING(
                    "This command is optimized for SMTP. Current backend may still work, but connection checks are skipped."
                )
            )
            return

        self.stdout.write(f"SMTP host: {settings.EMAIL_HOST or '(missing)'}")
        self.stdout.write(f"SMTP port: {settings.EMAIL_PORT}")
        self.stdout.write(f"TLS: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"SSL: {settings.EMAIL_USE_SSL}")
        self.stdout.write(f"SMTP user set: {bool(settings.EMAIL_HOST_USER)}")
        self.stdout.write(f"SMTP password set: {bool(settings.EMAIL_HOST_PASSWORD)}")

        missing = []
        if not settings.EMAIL_HOST:
            missing.append("EMAIL_HOST")
        if not settings.EMAIL_HOST_USER:
            missing.append("EMAIL_HOST_USER")
        if not settings.EMAIL_HOST_PASSWORD:
            missing.append("EMAIL_HOST_PASSWORD")
        if not settings.DEFAULT_FROM_EMAIL or "your-domain.com" in settings.DEFAULT_FROM_EMAIL:
            missing.append("DEFAULT_FROM_EMAIL")
        if not settings.SUPPORT_EMAIL or "your-domain.com" in settings.SUPPORT_EMAIL:
            missing.append("SUPPORT_EMAIL")
        if not settings.SITE_URL:
            missing.append("SITE_URL")

        if missing:
            self.stdout.write(
                self.style.WARNING(
                    "Missing or placeholder values: " + ", ".join(missing)
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Core SMTP settings look complete."))

        if not options["connect"]:
            return

        try:
            connection = get_connection()
            opened = connection.open()
            self.stdout.write(
                self.style.SUCCESS(
                    f"SMTP connection opened successfully (open returned {opened!r})."
                )
            )
            connection.close()
            self.stdout.write(self.style.SUCCESS("SMTP connection closed cleanly."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"SMTP connection failed: {exc}"))
