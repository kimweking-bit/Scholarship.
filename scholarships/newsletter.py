import logging

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import NewsletterSubscriber

logger = logging.getLogger(__name__)

NEWSLETTER_TOKEN_SALT = "scholarhub-newsletter"


def subscriber_greeting_name(subscriber: NewsletterSubscriber) -> str:
    if subscriber.user_id and subscriber.user:
        first_name = (subscriber.user.first_name or "").strip()
        if first_name:
            return first_name

        full_name = f"{subscriber.user.first_name} {subscriber.user.last_name}".strip()
        if full_name:
            return full_name

        username = (getattr(subscriber.user, "username", "") or "").strip()
        if username:
            return username

    local_part = subscriber.email.split("@", 1)[0]
    cleaned = local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return cleaned.title() or "there"


def newsletter_unsubscribe_token(email: str) -> str:
    normalized_email = (email or "").strip().lower()
    return signing.dumps({"email": normalized_email}, salt=NEWSLETTER_TOKEN_SALT)


def resolve_newsletter_token(token: str) -> str | None:
    try:
        payload = signing.loads(
            token,
            salt=NEWSLETTER_TOKEN_SALT,
            max_age=getattr(settings, "NEWSLETTER_TOKEN_MAX_AGE", 60 * 60 * 24 * 365 * 3),
        )
    except signing.BadSignature:
        return None
    except signing.SignatureExpired:
        return None

    email = str(payload.get("email", "")).strip().lower()
    return email or None


def absolute_url_for(request, path: str) -> str:
    if request is not None:
        return request.build_absolute_uri(path)

    base_url = getattr(settings, "SITE_URL", "").rstrip("/")
    if base_url:
        return f"{base_url}{path}"
    return path


def send_newsletter_welcome_email(subscriber: NewsletterSubscriber, *, request=None) -> None:
    unsubscribe_url = absolute_url_for(
        request,
        reverse("newsletter_unsubscribe", args=[newsletter_unsubscribe_token(subscriber.email)]),
    )
    scholarships_url = absolute_url_for(request, reverse("scholarships"))
    services_url = absolute_url_for(request, reverse("services"))
    dashboard_url = absolute_url_for(request, reverse("student_dashboard")) if subscriber.user_id else None
    register_url = absolute_url_for(request, reverse("register")) if not subscriber.user_id else None

    context = {
        "recipient_name": subscriber_greeting_name(subscriber),
        "scholarships_url": scholarships_url,
        "services_url": services_url,
        "dashboard_url": dashboard_url,
        "register_url": register_url,
        "unsubscribe_url": unsubscribe_url,
        "support_email": getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "site_url": getattr(settings, "SITE_URL", "").rstrip("/"),
        "year": timezone.now().year,
    }

    subject = "Welcome to ScholarHub. Your scholarship alerts are live."
    text_body = render_to_string("emails/newsletter_welcome.txt", context)
    html_body = render_to_string("emails/newsletter_welcome.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[subscriber.email],
        reply_to=[getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL)],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)

    subscriber.welcome_email_sent_at = timezone.now()
    subscriber.save(update_fields=["welcome_email_sent_at", "updated_at"])
    logger.info("Sent newsletter welcome email to %s", subscriber.email)
