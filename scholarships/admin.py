from django.contrib import admin, messages

from .newsletter import send_newsletter_welcome_email
from .models import (
    Application,
    ChatMessage,
    ChatThread,
    ContactMessage,
    NewsletterSubscriber,
    Scholarship,
)


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    @admin.display(boolean=True, ordering="deadline", description="Expired")
    def expired(self, obj: Scholarship) -> bool:
        return obj.is_expired

    list_display = ("title", "organization", "amount_display", "deadline", "expired", "is_active", "created_at")
    list_filter = ("is_active", "deadline")
    search_fields = ("title", "organization")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student_name", "email", "phone", "scholarship", "status", "user", "date_applied")
    list_filter = ("status", "date_applied", "scholarship")
    search_fields = ("student_name", "email", "phone", "scholarship__title", "user__username")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "email", "subject", "message")


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "user", "source", "is_active", "subscribed_at", "welcome_email_sent_at")
    list_filter = ("is_active", "source", "subscribed_at")
    search_fields = ("email", "user__username", "user__first_name", "user__last_name")
    actions = ("resend_welcome_email",)

    @admin.action(description="Resend ScholarHub welcome email")
    def resend_welcome_email(self, request, queryset):
        sent = 0
        failed = 0

        for subscriber in queryset:
            try:
                send_newsletter_welcome_email(subscriber, request=request)
                sent += 1
            except Exception:
                failed += 1

        if sent:
            self.message_user(request, f"Sent {sent} welcome email(s).", level=messages.SUCCESS)
        if failed:
            self.message_user(request, f"{failed} subscriber(s) could not be emailed.", level=messages.ERROR)


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("participant_name", "status", "last_message_at", "last_admin_reply_at", "last_user_message_at")
    list_filter = ("status", "last_message_at")
    search_fields = ("guest_label", "session_key", "user__username", "user__first_name", "user__last_name")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender_role", "sender_name", "created_at")
    list_filter = ("sender_role", "created_at")
    search_fields = ("sender_name", "body", "thread__guest_label", "thread__user__username")
