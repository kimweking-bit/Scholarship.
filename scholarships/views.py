import json
import logging
from datetime import datetime, timedelta
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.paginator import Paginator

from .categorization import infer_categories_from_text, infer_levels_from_text
from .forms import (
    ApplicationForm,
    ChatMessageForm,
    NewsletterSubscriptionForm,
    ScholarshipForm,
    StudentProfileForm,
    UserUpdateForm,
)
from .models import (
    Application,
    ApplicationAttachment,
    ChatMessage,
    ChatThread,
    ContactMessage,
    NewsletterSubscriber,
    Notification,
    Scholarship,
    StudentProfile,
)
from .newsletter import resolve_newsletter_token, send_newsletter_welcome_email

logger = logging.getLogger(__name__)


class RoleBasedLoginView(LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url
        if self.request.user.is_staff:
            return reverse("admin_dashboard")
        return reverse("student_dashboard")


def auto_deactivate_expired_scholarships() -> int:
    """
    Keep expired scholarships out of the public experience by deactivating them.

    This is intentionally lightweight (single UPDATE) and can be called at the start
    of request handlers in lieu of a scheduler.
    """
    today = timezone.localdate()
    return Scholarship.objects.filter(is_active=True, deadline__lt=today).update(is_active=False)


def available_scholarships_qs():
    today = timezone.localdate()
    return Scholarship.objects.filter(is_active=True).filter(Q(deadline__isnull=True) | Q(deadline__gte=today))


def funding_bucket(value: str) -> str:
    text = (value or "").strip().lower()
    if not text or text == "-":
        return "Open Support"
    if any(token in text for token in ("full", "fully", "100%", "all expenses", "complete funding")):
        return "Fully Funded"
    if any(token in text for token in ("partial", "stipend", "grant", "tuition", "allowance", "support", "bursary")):
        return "Partial Support"
    return "Funding Available"


def truncate_words(text: str, limit: int = 18) -> str:
    words = [word for word in (text or "").split() if word]
    if not words:
        return ""
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + "..."


def scholarship_card_payload(scholarship: Scholarship, *, profile: StudentProfile | None, recommended: bool, today: date):
    preferred_country = (getattr(profile, "preferred_country", "") or "").strip().lower()
    preferred_level = (getattr(profile, "preferred_level", "") or "").strip().lower()
    course_kw = (getattr(profile, "course", "") or "").strip().lower()

    searchable_text = " ".join(
        filter(
            None,
            [
                scholarship.title,
                scholarship.organization,
                scholarship.country,
                scholarship.level,
                scholarship.category,
                scholarship.description,
                scholarship.requirements,
            ],
        )
    ).lower()

    score = 68 if recommended else 61
    reasons = []

    if preferred_country and scholarship.country and preferred_country in scholarship.country.lower():
        score += 14
        reasons.append(f"Matches your preferred country: {scholarship.country}")

    if preferred_level and scholarship.level and preferred_level == scholarship.level.lower():
        score += 12
        reasons.append(f"Aligned with your preferred level: {scholarship.get_level_display()}")

    if course_kw and course_kw in searchable_text:
        score += 18
        reasons.append("Keywords from your course appear in the scholarship details")

    if scholarship.category and course_kw and scholarship.category.lower() in course_kw:
        score += 8
        reasons.append(f"Strong category fit in {scholarship.category}")

    completeness = sum(
        1
        for value in [
            scholarship.organization,
            scholarship.country,
            scholarship.level,
            scholarship.amount_display or scholarship.amount,
            scholarship.description,
        ]
        if value
    )
    score += min(10, completeness * 2)

    funding_label = funding_bucket(scholarship.funding)
    if funding_label == "Fully Funded":
        score += 6

    days_left = None
    deadline_label = "Rolling deadline"
    if scholarship.deadline:
        days_left = max((scholarship.deadline - today).days, 0)
        if days_left == 0:
            deadline_label = "Closes today"
        elif days_left == 1:
            deadline_label = "1 day left"
        else:
            deadline_label = f"{days_left} days left"

        if days_left <= 14:
            score += 6

    score = max(52, min(score, 98))

    badges = []
    if recommended:
        badges.append({"label": "AI Recommended", "tone": "ai", "icon": "bi-stars"})
    if score >= 85:
        badges.append({"label": "High Match", "tone": "match", "icon": "bi-lightning-charge-fill"})
    elif score >= 74:
        badges.append({"label": "Best for You", "tone": "match", "icon": "bi-magic"})
    if days_left is not None and days_left <= 14:
        badges.append({"label": "Closing Soon", "tone": "urgent", "icon": "bi-hourglass-split"})
    if funding_label == "Fully Funded":
        badges.append({"label": "Fully Funded", "tone": "funding", "icon": "bi-cash-stack"})

    summary_source = (scholarship.description or "").strip() or (scholarship.requirements or "").strip()
    if not summary_source:
        summary_source = f"{scholarship.title} from {scholarship.university} with {funding_label.lower()} support."

    ai_reason = reasons[0] if reasons else (
        "Recommended from your dashboard activity and open opportunity signals"
        if recommended
        else "Fresh opportunity worth exploring in your broader search"
    )

    return {
        "scholarship": scholarship,
        "match_score": score,
        "funding_bucket": funding_label,
        "days_left": days_left,
        "deadline_label": deadline_label,
        "level_label": scholarship.get_level_display() if scholarship.level else "Open level",
        "summary": truncate_words(summary_source, 20),
        "ai_reason": ai_reason,
        "badges": badges[:3],
    }


def build_quick_filters(*, profile: StudentProfile | None, countries, levels, funding_labels):
    chips = []
    seen = set()

    def add_chip(filter_type: str, value: str, label: str, icon: str):
        if not value:
            return
        key = (filter_type, value.lower())
        if key in seen:
            return
        seen.add(key)
        chips.append({"type": filter_type, "value": value, "label": label, "icon": icon})

    if profile:
        add_chip("country", (profile.preferred_country or "").strip(), (profile.preferred_country or "").strip(), "bi-geo-alt")
        add_chip("degree", (profile.preferred_level or "").strip(), (profile.preferred_level or "").strip(), "bi-mortarboard")

    if "Fully Funded" in funding_labels:
        add_chip("funding", "Fully Funded", "Fully Funded", "bi-cash-stack")

    for country in countries[:2]:
        add_chip("country", country, country, "bi-globe2")

    for level in levels[:1]:
        add_chip("degree", level, level, "bi-award")

    return chips[:5]


def sanitized_newsletter_source(raw_value: str) -> str:
    candidate = "".join(ch for ch in (raw_value or "").strip().lower() if ch.isalnum() or ch in {"-", "_"})
    return candidate[:80]


def safe_next_url(request) -> str:
    next_url = (request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse("home")


def newsletter_redirect_url(target_url: str, *, status: str, source: str = "", anchor: str = "") -> str:
    parts = urlsplit(target_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["newsletter"] = status
    if source:
        query["newsletter_source"] = source
    else:
        query.pop("newsletter_source", None)

    safe_anchor = "".join(ch for ch in (anchor or "").strip() if ch.isalnum() or ch in {"-", "_"})
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, doseq=True),
            safe_anchor or parts.fragment,
        )
    )


def ensure_session_key(request) -> str:
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key or ""
    return session_key or ""


def thread_participant_label(request) -> str:
    if request.user.is_authenticated:
        full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        return full_name or getattr(request.user, "username", "") or "Student"
    return "Guest visitor"


def remember_chat_thread(request, thread: ChatThread | None) -> None:
    if thread is None:
        request.session.pop("chat_thread_id", None)
        return
    request.session["chat_thread_id"] = thread.id


def get_chat_thread_for_request(request, *, create: bool = False) -> ChatThread | None:
    session_key = ensure_session_key(request) if create or not request.user.is_authenticated else (request.session.session_key or "")
    remembered_thread_id = request.session.get("chat_thread_id")
    participant_label = thread_participant_label(request)

    if request.user.is_authenticated:
        thread = (
            ChatThread.objects.filter(user=request.user)
            .order_by("-last_message_at", "-updated_at")
            .first()
        )
        if thread:
            if session_key and thread.session_key != session_key:
                thread.session_key = session_key
                thread.save(update_fields=["session_key", "updated_at"])
            remember_chat_thread(request, thread)
            return thread

        if remembered_thread_id:
            remembered_thread = ChatThread.objects.filter(id=remembered_thread_id).first()
            if remembered_thread and (remembered_thread.user_id in {None, request.user.id}):
                update_fields = []
                if remembered_thread.user_id != request.user.id:
                    remembered_thread.user = request.user
                    update_fields.append("user")
                if remembered_thread.guest_label != participant_label:
                    remembered_thread.guest_label = participant_label
                    update_fields.append("guest_label")
                if session_key and remembered_thread.session_key != session_key:
                    remembered_thread.session_key = session_key
                    update_fields.append("session_key")
                if update_fields:
                    remembered_thread.save(update_fields=update_fields + ["updated_at"])
                remember_chat_thread(request, remembered_thread)
                return remembered_thread

        session_thread = None
        if session_key:
            session_thread = (
                ChatThread.objects.filter(user__isnull=True, session_key=session_key)
                .order_by("-last_message_at", "-updated_at")
                .first()
            )
        if session_thread:
            session_thread.user = request.user
            session_thread.guest_label = participant_label
            session_thread.save(update_fields=["user", "guest_label", "updated_at"])
            remember_chat_thread(request, session_thread)
            return session_thread

        if create:
            thread = ChatThread.objects.create(
                user=request.user,
                session_key=session_key,
                guest_label=participant_label,
            )
            remember_chat_thread(request, thread)
            return thread
        return None

    if not session_key:
        return None

    if remembered_thread_id:
        remembered_thread = ChatThread.objects.filter(id=remembered_thread_id, user__isnull=True).first()
        if remembered_thread:
            update_fields = []
            if remembered_thread.session_key != session_key:
                remembered_thread.session_key = session_key
                update_fields.append("session_key")
            if remembered_thread.guest_label != participant_label:
                remembered_thread.guest_label = participant_label
                update_fields.append("guest_label")
            if update_fields:
                remembered_thread.save(update_fields=update_fields + ["updated_at"])
            remember_chat_thread(request, remembered_thread)
            return remembered_thread

    thread = (
        ChatThread.objects.filter(user__isnull=True, session_key=session_key)
        .order_by("-last_message_at", "-updated_at")
        .first()
    )
    if thread:
        remember_chat_thread(request, thread)
        return thread

    if create:
        thread = ChatThread.objects.create(
            session_key=session_key,
            guest_label=participant_label,
        )
        remember_chat_thread(request, thread)
        return thread
    return None


def serialize_chat_message(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "sender_role": message.sender_role,
        "sender_name": message.sender_name or ("Admin" if message.sender_role == ChatMessage.SENDER_ADMIN else "You"),
        "body": message.body,
        "created_at": timezone.localtime(message.created_at).strftime("%b %d, %Y %I:%M %p"),
    }


def unread_user_message_count(thread: ChatThread) -> int:
    return thread.messages.filter(sender_role=ChatMessage.SENDER_USER, read_by_admin_at__isnull=True).count()


@ensure_csrf_cookie
def index(request):
    auto_deactivate_expired_scholarships()
    User = get_user_model()
    scholarships_qs = available_scholarships_qs()

    total_scholarships = scholarships_qs.count()
    total_students = User.objects.filter(is_staff=False).count()
    total_countries = scholarships_qs.exclude(country="").values("country").distinct().count()
    total_universities = scholarships_qs.exclude(organization="").values("organization").distinct().count()
    total_applications = Application.objects.count()

    funding_sum = scholarships_qs.aggregate(s=Sum("amount")).get("s") or 0
    try:
        funding_float = float(funding_sum)
    except Exception:
        funding_float = 0.0

    if funding_float >= 1_000_000:
        total_funding = f"${funding_float / 1_000_000:.1f}M"
    elif funding_float >= 1_000:
        total_funding = f"${funding_float:,.0f}"
    else:
        total_funding = f"${funding_float:.0f}"

    featured_scholarships = scholarships_qs[:3]

    return render(
        request,
        "index.html",
        {
            "featured_scholarships": featured_scholarships,
            # Template-friendly alias for homepage sections that expect `scholarships`.
            "scholarships": featured_scholarships,
            "total_scholarships": total_scholarships,
            "total_students": total_students,
            "total_countries": total_countries,
            "total_universities": total_universities,
            "total_funding": total_funding,
            "total_applications": total_applications,
        },
    )


def scholarships_list(request):
    q = (request.GET.get("q") or "").strip()
    country = (request.GET.get("country") or "").strip()
    level = (request.GET.get("level") or "").strip()
    category = (request.GET.get("category") or "").strip()
    deadline_before_raw = (request.GET.get("deadline_before") or "").strip()
    deadline_after_raw = (request.GET.get("deadline_after") or "").strip()

    auto_deactivate_expired_scholarships()
    qs = available_scholarships_qs()

    if country:
        qs = qs.filter(country__icontains=country)

    if level:
        allowed = {c[0] for c in Scholarship.LEVEL_CHOICES}
        label_to_value = {label.lower(): value for value, label in Scholarship.LEVEL_CHOICES}
        if level in allowed:
            qs = qs.filter(level=level)
        else:
            # Accept UI labels (e.g., "Degree") and common terms, and map them to stored values.
            mapped = label_to_value.get(level.lower())
            if mapped:
                qs = qs.filter(level=mapped)
            else:
                inferred = infer_levels_from_text(level)
                if inferred:
                    qs = qs.filter(level__in=inferred)

    if category:
        allowed = {c[0] for c in Scholarship.CATEGORY_CHOICES}
        if category in allowed:
            qs = qs.filter(category=category)
        else:
            # Accept common search terms (e.g., "engineering") and map them to known categories.
            inferred = infer_categories_from_text(category)
            if inferred:
                qs = qs.filter(category__in=inferred)
            else:
                # Case-insensitive exact match against allowed values.
                match = next((v for v in allowed if v.lower() == category.lower()), None)
                if match:
                    qs = qs.filter(category=match)

    deadline_before = None
    if deadline_before_raw:
        try:
            deadline_before = date.fromisoformat(deadline_before_raw)
        except ValueError:
            deadline_before = None

    deadline_after = None
    if deadline_after_raw:
        try:
            deadline_after = date.fromisoformat(deadline_after_raw)
        except ValueError:
            deadline_after = None

    if deadline_before:
        qs = qs.filter(Q(deadline__isnull=True) | Q(deadline__lte=deadline_before))

    if deadline_after:
        qs = qs.filter(Q(deadline__isnull=True) | Q(deadline__gte=deadline_after))

    if q:
        inferred = infer_categories_from_text(q)
        inferred_levels = infer_levels_from_text(q)
        q_filter = (
            Q(title__icontains=q)
            | Q(organization__icontains=q)
            | Q(country__icontains=q)
            | Q(description__icontains=q)
            | Q(requirements__icontains=q)
            | Q(category__icontains=q)
            | Q(level__icontains=q)
            | Q(amount_display__icontains=q)
        )
        if inferred:
            q_filter |= Q(category__in=inferred)
        if inferred_levels:
            q_filter |= Q(level__in=inferred_levels)
        qs = qs.filter(q_filter)

    country_options = (
        Scholarship.objects.exclude(country="")
        .values_list("country", flat=True)
        .distinct()
        .order_by("country")
    )

    # Paginate at 9 cards per page; get_page gracefully handles invalid or out-of-range page numbers.
    paginator = Paginator(qs, 9)
    page_number = request.GET.get("page") or 1
    scholarships_page = paginator.get_page(page_number)

    return render(
        request,
        "scholarships.html",
        {
            "scholarships": scholarships_page,  # Page object supports iteration and pagination attrs
            "q": q,
            "country": country,
            "level": level,
            "category": category,
            "deadline_before": deadline_before_raw,
            "deadline_after": deadline_after_raw,
            "country_options": list(country_options),
            "level_options": Scholarship.LEVEL_CHOICES,
            "category_options": Scholarship.CATEGORY_CHOICES,
        },
    )


def about(request):
    return render(request, "about.html")


def services(request):
    return render(request, "services.html")


@require_POST
@csrf_protect
def subscribe_newsletter(request):
    form = NewsletterSubscriptionForm(request.POST)
    redirect_target = safe_next_url(request)
    source = sanitized_newsletter_source(request.POST.get("source") or "")
    anchor = request.POST.get("anchor") or "newsletter"

    if not form.is_valid():
        return redirect(newsletter_redirect_url(redirect_target, status="invalid", source=source, anchor=anchor))

    email = form.cleaned_data["email"].strip().lower()
    subscriber = NewsletterSubscriber.objects.filter(email__iexact=email).first()
    created = False
    if subscriber is None:
        subscriber = NewsletterSubscriber.objects.create(
            email=email,
            user=request.user if request.user.is_authenticated else None,
            source=source,
        )
        created = True

    should_send_welcome = created
    status = "success"
    update_fields = []

    if subscriber.email != email:
        subscriber.email = email
        update_fields.append("email")

    if request.user.is_authenticated and subscriber.user_id != request.user.id:
        subscriber.user = request.user
        update_fields.append("user")

    if source and subscriber.source != source:
        subscriber.source = source
        update_fields.append("source")

    if not subscriber.is_active:
        subscriber.is_active = True
        update_fields.append("is_active")
        should_send_welcome = True
        status = "resubscribed"

    if update_fields:
        subscriber.save(update_fields=update_fields + ["updated_at"])

    if not should_send_welcome and subscriber.is_active:
        status = "exists"

    if should_send_welcome:
        try:
            send_newsletter_welcome_email(subscriber, request=request)
        except Exception:
            logger.exception("Newsletter welcome email failed for %s", subscriber.email)
            status = "delivery_issue"

    return redirect(newsletter_redirect_url(redirect_target, status=status, source=source, anchor=anchor))


def newsletter_unsubscribe(request, token: str):
    email = resolve_newsletter_token(token)
    subscriber = None
    status = "invalid"

    if email:
        subscriber = NewsletterSubscriber.objects.filter(email__iexact=email).first()
        if subscriber:
            if subscriber.is_active:
                subscriber.is_active = False
                subscriber.save(update_fields=["is_active", "updated_at"])
                status = "success"
            else:
                status = "already"

    return render(
        request,
        "newsletter_unsubscribe.html",
        {
            "status": status,
            "subscriber": subscriber,
        },
    )


@csrf_protect
def contact(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        subject = (request.POST.get("subject") or "").strip()
        message = (request.POST.get("message") or "").strip()

        if name and email and message:
            ContactMessage.objects.create(name=name, email=email, subject=subject, message=message)
            return render(request, "contact.html", {"success": True})

        return render(
            request,
            "contact.html",
            {"error": True, "name": name, "email": email, "subject": subject, "message": message},
        )

    return render(request, "contact.html")


@ensure_csrf_cookie
def chat_state(request):
    thread = get_chat_thread_for_request(request, create=False)
    if not thread:
        remember_chat_thread(request, None)
        return JsonResponse(
            {
                "thread_id": None,
                "status": ChatThread.STATUS_OPEN,
                "participant_name": thread_participant_label(request),
                "messages": [],
            }
        )

    ChatMessage.objects.filter(
        thread=thread,
        sender_role=ChatMessage.SENDER_ADMIN,
        read_by_user_at__isnull=True,
    ).update(read_by_user_at=timezone.now())
    remember_chat_thread(request, thread)

    messages = [serialize_chat_message(message) for message in thread.messages.all()]
    return JsonResponse(
        {
            "thread_id": thread.id,
            "status": thread.status,
            "participant_name": thread.participant_name,
            "messages": messages,
        }
    )


@require_POST
@csrf_protect
def chat_send(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = request.POST

    form = ChatMessageForm(payload)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    thread = get_chat_thread_for_request(request, create=True)
    if thread is None:
        return JsonResponse({"ok": False, "errors": {"body": ["Unable to open a chat thread."]}}, status=400)

    now = timezone.now()
    if thread.status != ChatThread.STATUS_OPEN:
        thread.status = ChatThread.STATUS_OPEN

    thread.guest_label = thread_participant_label(request)
    thread.last_message_at = now
    thread.last_user_message_at = now
    thread.save(update_fields=["status", "guest_label", "last_message_at", "last_user_message_at", "updated_at"])

    message = ChatMessage.objects.create(
        thread=thread,
        sender_role=ChatMessage.SENDER_USER,
        sender_name=thread.participant_name,
        body=form.cleaned_data["body"],
        read_by_user_at=now,
    )
    remember_chat_thread(request, thread)

    return JsonResponse(
        {
            "ok": True,
            "thread_id": thread.id,
            "message": serialize_chat_message(message),
        }
    )


@staff_member_required
def admin_chat(request):
    selected_thread_id = request.GET.get("thread") or request.POST.get("thread_id")
    threads = list(
        ChatThread.objects.select_related("user").prefetch_related("messages").all()
    )
    selected_thread = next((thread for thread in threads if str(thread.id) == str(selected_thread_id)), None)
    if selected_thread is None and threads:
        selected_thread = threads[0]

    reply_form = ChatMessageForm()

    if request.method == "POST" and selected_thread:
        action = (request.POST.get("action") or "reply").strip().lower()
        if action in {"resolve", "reopen"}:
            selected_thread.status = ChatThread.STATUS_RESOLVED if action == "resolve" else ChatThread.STATUS_OPEN
            selected_thread.save(update_fields=["status", "updated_at"])
            return redirect(f"{request.path}?thread={selected_thread.id}")

        reply_form = ChatMessageForm(request.POST)
        if reply_form.is_valid():
            sender_name = (f"{request.user.first_name} {request.user.last_name}").strip() or request.user.username
            now = timezone.now()
            ChatMessage.objects.create(
                thread=selected_thread,
                sender_role=ChatMessage.SENDER_ADMIN,
                sender_name=sender_name,
                body=reply_form.cleaned_data["body"],
                read_by_admin_at=now,
            )
            selected_thread.status = ChatThread.STATUS_OPEN
            selected_thread.last_message_at = now
            selected_thread.last_admin_reply_at = now
            selected_thread.save(update_fields=["status", "last_message_at", "last_admin_reply_at", "updated_at"])
            return redirect(f"{request.path}?thread={selected_thread.id}")

    if selected_thread:
        ChatMessage.objects.filter(
            thread=selected_thread,
            sender_role=ChatMessage.SENDER_USER,
            read_by_admin_at__isnull=True,
        ).update(read_by_admin_at=timezone.now())

    thread_cards = []
    for thread in threads:
        messages = list(thread.messages.all())
        latest_message = messages[-1] if messages else None
        thread_cards.append(
            {
                "thread": thread,
                "latest_message": latest_message,
                "unread_count": unread_user_message_count(thread),
            }
        )

    open_thread_count = sum(1 for thread in threads if thread.status == ChatThread.STATUS_OPEN)
    unread_thread_count = sum(1 for item in thread_cards if item["unread_count"] > 0)

    return render(
        request,
        "admin_chat.html",
        {
            "thread_cards": thread_cards,
            "selected_thread": selected_thread,
            "reply_form": reply_form,
            "open_thread_count": open_thread_count,
            "unread_thread_count": unread_thread_count,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("student_dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("student_dashboard")
    else:
        form = UserCreationForm()

    return render(request, "register.html", {"form": form})


@staff_member_required
def admin_dashboard(request):
    auto_deactivate_expired_scholarships()
    User = get_user_model()

    applications_qs = Application.objects.select_related("scholarship", "user").all()
    scholarships_qs = Scholarship.objects.all()
    chat_threads_qs = ChatThread.objects.all()

    total_scholarships = scholarships_qs.count()
    total_students = User.objects.filter(is_staff=False).count()
    total_applications = applications_qs.count()
    approved_applications = applications_qs.filter(status=Application.STATUS_APPROVED).count()
    open_chat_threads = chat_threads_qs.filter(status=ChatThread.STATUS_OPEN).count()
    unread_chat_threads = (
        ChatMessage.objects.filter(sender_role=ChatMessage.SENDER_USER, read_by_admin_at__isnull=True)
        .values("thread_id")
        .distinct()
        .count()
    )

    recent_applications = applications_qs[:12]
    recent_scholarships = scholarships_qs[:12]

    # Applications overview: last 6 months (including current month).
    today = timezone.localdate()
    months = []
    cursor = today.replace(day=1)
    for _ in range(6):
        months.append(cursor)
        cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
    months = list(reversed(months))

    month_labels = [m.strftime("%b") for m in months]
    month_index = {m: i for i, m in enumerate(months)}
    month_counts = [0] * len(months)

    start_dt = timezone.make_aware(datetime(months[0].year, months[0].month, 1))
    agg = (
        applications_qs.filter(date_applied__gte=start_dt)
        .annotate(m=TruncMonth("date_applied"))
        .values("m")
        .annotate(c=Count("id"))
        .order_by("m")
    )
    for row in agg:
        m = row["m"]
        if not m:
            continue
        key = timezone.localdate(m).replace(day=1)
        idx = month_index.get(key)
        if idx is not None:
            month_counts[idx] = row["c"]

    # Scholarships by country: top 4 + "Other".
    raw = (
        scholarships_qs.values("country")
        .annotate(c=Count("id"))
        .order_by("-c")
    )
    by_country = {}
    for row in raw:
        ctry = (row["country"] or "").strip() or "Unknown"
        by_country[ctry] = by_country.get(ctry, 0) + row["c"]

    items = sorted(by_country.items(), key=lambda x: x[1], reverse=True)
    top = items[:4]
    other = sum(v for _, v in items[4:])
    country_labels = [k for k, _ in top] + (["Other"] if other else [])
    country_counts = [v for _, v in top] + ([other] if other else [])

    return render(
        request,
        "admin_dashboard.html",
        {
            "total_scholarships": total_scholarships,
            "total_students": total_students,
            "total_applications": total_applications,
            "approved_applications": approved_applications,
            "recent_applications": recent_applications,
            "recent_scholarships": recent_scholarships,
            "applications_chart": {"labels": month_labels, "data": month_counts},
            "country_chart": {"labels": country_labels, "data": country_counts},
            "open_chat_threads": open_chat_threads,
            "unread_chat_threads": unread_chat_threads,
        },
    )


@login_required
def student_dashboard(request):
    auto_deactivate_expired_scholarships()
    scholarships_qs = available_scholarships_qs()
    user_apps_qs = Application.objects.select_related("scholarship").filter(user=request.user)
    today = timezone.localdate()
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_scholarships = scholarships_qs.count()
    applied_count = user_apps_qs.count()
    pending_count = user_apps_qs.filter(status=Application.STATUS_PENDING).count()
    approved_count = user_apps_qs.filter(status=Application.STATUS_APPROVED).count()
    new_scholarships_week = scholarships_qs.filter(created_at__gte=week_ago).count()
    applied_this_week = user_apps_qs.filter(date_applied__gte=week_ago).count()
    approved_this_month = user_apps_qs.filter(
        status=Application.STATUS_APPROVED,
        date_applied__gte=month_ago,
    ).count()

    profile = StudentProfile.objects.filter(user=request.user).first()
    rec_qs = scholarships_qs.exclude(applications__user=request.user)
    if profile:
        if profile.preferred_country.strip():
            rec_qs = rec_qs.filter(country__icontains=profile.preferred_country.strip())
        if profile.preferred_level.strip():
            rec_qs = rec_qs.filter(level=profile.preferred_level.strip())
        if profile.course.strip():
            kw = profile.course.strip()
            rec_qs = rec_qs.filter(
                Q(title__icontains=kw) | Q(description__icontains=kw) | Q(requirements__icontains=kw)
            )

    recommended_scholarships = list(rec_qs[:6])
    if not recommended_scholarships:
        recommended_scholarships = list(scholarships_qs.exclude(applications__user=request.user)[:6])

    recommended_ids = [scholarship.id for scholarship in recommended_scholarships]
    discover_qs = scholarships_qs.exclude(id__in=recommended_ids) if recommended_ids else scholarships_qs
    discover_scholarships = list(discover_qs[:12])
    if not discover_scholarships:
        discover_scholarships = list(scholarships_qs[:12])

    recommended_cards = [
        scholarship_card_payload(scholarship, profile=profile, recommended=True, today=today)
        for scholarship in recommended_scholarships
    ]
    discover_cards = [
        scholarship_card_payload(scholarship, profile=profile, recommended=False, today=today)
        for scholarship in discover_scholarships
    ]

    country_options = list(
        scholarships_qs.exclude(country="").values_list("country", flat=True).distinct().order_by("country")[:8]
    )
    level_options = list(
        scholarships_qs.exclude(level="").values_list("level", flat=True).distinct().order_by("level")[:6]
    )
    funding_options = []
    for scholarship in scholarships_qs[:20]:
        label = funding_bucket(scholarship.funding)
        if label not in funding_options:
            funding_options.append(label)

    quick_filters = build_quick_filters(
        profile=profile,
        countries=country_options,
        levels=level_options,
        funding_labels=funding_options,
    )

    next_deadline = scholarships_qs.exclude(applications__user=request.user).filter(deadline__isnull=False).order_by("deadline").first()
    next_deadline_days = None
    if next_deadline and next_deadline.deadline:
        next_deadline_days = max((next_deadline.deadline - today).days, 0)

    approval_rate = int(round((approved_count / applied_count) * 100)) if applied_count else 0
    journey_percent = min(100, 18 + (applied_count * 14) + (approved_count * 10) + (12 if profile else 0))
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    recent_notifications = Notification.objects.filter(user=request.user).all()[:5]
    support_thread = get_chat_thread_for_request(request, create=False)
    support_messages_preview = []
    unread_chat_replies = 0
    latest_chat_message = None
    if support_thread:
        support_messages_preview = list(support_thread.messages.order_by("-created_at")[:4])
        support_messages_preview.reverse()
        unread_chat_replies = support_thread.messages.filter(
            sender_role=ChatMessage.SENDER_ADMIN,
            read_by_user_at__isnull=True,
        ).count()
        latest_chat_message = support_messages_preview[-1] if support_messages_preview else None

    return render(
        request,
        "student_dashboard.html",
        {
            "total_scholarships": total_scholarships,
            "applied_count": applied_count,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "new_scholarships_week": new_scholarships_week,
            "applied_this_week": applied_this_week,
            "approved_this_month": approved_this_month,
            "approval_rate": approval_rate,
            "journey_percent": journey_percent,
            "profile": profile,
            "applications": user_apps_qs[:5],
            "recommended_cards": recommended_cards,
            "discover_cards": discover_cards,
            "country_options": country_options,
            "level_options": level_options,
            "funding_options": funding_options,
            "quick_filters": quick_filters,
            "next_deadline": next_deadline,
            "next_deadline_days": next_deadline_days,
            "unread_notifications": unread_notifications,
            "recent_notifications": recent_notifications,
            "support_thread": support_thread,
            "support_messages_preview": support_messages_preview,
            "unread_chat_replies": unread_chat_replies,
            "support_message_count": support_thread.messages.count() if support_thread else 0,
            "latest_chat_message": latest_chat_message,
        },
    )


@staff_member_required
@require_POST
def delete_scholarship(request, id: int):
    scholarship = get_object_or_404(Scholarship, id=id)
    scholarship.delete()
    return redirect("admin_dashboard")


@login_required
def my_applications(request):
    applications = (
        Application.objects.select_related("scholarship")
        .filter(user=request.user)
        .all()
    )
    return render(request, "my_applications.html", {"applications": applications})


@login_required
def apply_scholarship(request, id: int):
    scholarship = get_object_or_404(Scholarship, id=id)
    profile = StudentProfile.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.scholarship = scholarship
            application.user = request.user

            if not application.email and getattr(request.user, "email", ""):
                application.email = request.user.email

            use_profile_cv = (request.POST.get("use_profile_cv") or "").strip().lower() in {"1", "true", "on", "yes"}
            if use_profile_cv and not application.cv and profile and profile.cv:
                # Point to the same stored file; this keeps storage simple for this project.
                application.cv = profile.cv

            application.save()

            for f in request.FILES.getlist("academic_documents"):
                if not f:
                    continue
                ApplicationAttachment.objects.create(
                    application=application,
                    kind=ApplicationAttachment.KIND_ACADEMIC,
                    label=getattr(f, "name", "") or "",
                    file=f,
                )

            return redirect("student_dashboard")
    else:
        initial = {}
        if request.user.is_authenticated:
            # Best-effort prefill; safe if the user model doesn't have first/last/email set.
            student_name = (f"{request.user.first_name} {request.user.last_name}").strip()
            if student_name:
                initial["student_name"] = student_name
            if getattr(request.user, "email", ""):
                initial["email"] = request.user.email
        form = ApplicationForm(initial=initial)

    return render(request, "apply.html", {"form": form, "scholarship": scholarship, "profile": profile})


@staff_member_required
@require_POST
def approve_application(request, id: int):
    application = get_object_or_404(Application, id=id)
    application.status = Application.STATUS_APPROVED
    application.save(update_fields=["status"])
    return redirect("admin_dashboard")


@staff_member_required
@require_POST
def reject_application(request, id: int):
    application = get_object_or_404(Application, id=id)
    application.status = Application.STATUS_REJECTED
    application.save(update_fields=["status"])
    return redirect("admin_dashboard")


@staff_member_required
def create_scholarship(request):
    if request.method == "POST":
        form = ScholarshipForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("admin_dashboard")
    else:
        form = ScholarshipForm()

    return render(request, "create_scholarship.html", {"form": form})


@staff_member_required
def admin_scholarships(request):
    return redirect("admin_dashboard")


@staff_member_required
def edit_scholarship(request, id: int):
    scholarship = get_object_or_404(Scholarship, id=id)
    if request.method == "POST":
        form = ScholarshipForm(request.POST, request.FILES, instance=scholarship)
        if form.is_valid():
            form.save()
            return redirect("admin_dashboard")
    else:
        form = ScholarshipForm(instance=scholarship)

    return render(request, "create_scholarship.html", {"form": form, "scholarship": scholarship})


@staff_member_required
@require_POST
def toggle_scholarship_active(request, id: int):
    scholarship = get_object_or_404(Scholarship, id=id)
    scholarship.is_active = not scholarship.is_active
    scholarship.save(update_fields=["is_active"])
    return redirect(request.POST.get("next") or "admin_dashboard")


@login_required
def profile(request):
    prof, _ = StudentProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = StudentProfileForm(request.POST, request.FILES, instance=prof)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect("student_dashboard")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = StudentProfileForm(instance=prof)

    return render(request, "profile.html", {"user_form": user_form, "profile_form": profile_form})


@login_required
def notifications(request):
    qs = Notification.objects.filter(user=request.user).all()[:200]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, "notifications.html", {"notifications": qs, "unread_count": unread_count})


@login_required
@require_POST
def notification_mark_read(request, id: int):
    notif = get_object_or_404(Notification, id=id, user=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    return redirect("notifications")


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications")
