from django.contrib import admin

from .models import Application, ContactMessage, Scholarship


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
