from django.conf import settings
from django.db import models
from django.utils import timezone


class Scholarship(models.Model):
    LEVEL_UNDERGRADUATE = "Undergraduate"
    LEVEL_MASTERS = "Masters"
    LEVEL_PHD = "PhD"
    LEVEL_DIPLOMA = "Diploma"
    LEVEL_CERTIFICATE = "Certificate"
    LEVEL_POSTDOC = "Postdoc"
    LEVEL_OTHER = "Other"
    LEVEL_CHOICES = [
        # Stored value remains "Undergraduate" for compatibility; display label is "Degree".
        (LEVEL_UNDERGRADUATE, "Degree"),
        (LEVEL_MASTERS, "Masters"),
        (LEVEL_PHD, "PhD"),
        (LEVEL_DIPLOMA, "Diploma"),
        (LEVEL_CERTIFICATE, "Certificate"),
        (LEVEL_POSTDOC, "Postdoc"),
        (LEVEL_OTHER, "Other"),
    ]

    CATEGORY_STEM = "STEM"
    CATEGORY_BUSINESS = "Business"
    CATEGORY_ARTS = "Arts & Humanities"
    CATEGORY_MEDICINE = "Medicine & Health"
    CATEGORY_SOCIAL = "Social Sciences"
    CATEGORY_LAW = "Law"
    CATEGORY_EDUCATION = "Education"
    CATEGORY_OTHER = "Other"
    CATEGORY_CHOICES = [
        (CATEGORY_STEM, "Engineering & Tech"),
        (CATEGORY_BUSINESS, "Business"),
        (CATEGORY_ARTS, "Arts & Humanities"),
        (CATEGORY_MEDICINE, "Medicine & Health"),
        (CATEGORY_SOCIAL, "Social Sciences"),
        (CATEGORY_LAW, "Law"),
        (CATEGORY_EDUCATION, "Education"),
        (CATEGORY_OTHER, "Other"),
    ]

    title = models.CharField(max_length=200)
    organization = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=100, blank=True)
    level = models.CharField(max_length=30, choices=LEVEL_CHOICES, blank=True, default="")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, default="")
    deadline = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # For values like "Full Scholarship" or "KES 150,000 per year" where a pure number isn't enough.
    amount_display = models.CharField(max_length=200, blank=True)
    requirements = models.TextField(blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="scholarship_images/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def university(self) -> str:
        # Template-friendly alias for older markup that expects `university`.
        return (self.organization or "").strip() or "-"

    @property
    def funding(self) -> str:
        # Template-friendly alias for older markup that expects `funding`.
        if (self.amount_display or "").strip():
            return self.amount_display.strip()
        if self.amount is not None:
            # Keep it simple; callers can format if needed.
            return str(self.amount)
        return "-"

    @property
    def is_expired(self) -> bool:
        """
        Consider a scholarship expired if it has a deadline and that date is in the past.
        (Null deadlines are treated as "not expired".)
        """
        if not self.deadline:
            return False
        return self.deadline < timezone.localdate()


class Application(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE, related_name="applications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scholarship_applications")

    student_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    motivation_letter = models.TextField(blank=True)
    cv = models.FileField(upload_to="cv/", blank=True, null=True)
    picture = models.ImageField(upload_to="pictures/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    date_applied = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_applied"]

    def __str__(self) -> str:
        return f"{self.student_name} -> {self.scholarship.title}"


class ApplicationAttachment(models.Model):
    KIND_ACADEMIC = "Academic"
    KIND_OTHER = "Other"
    KIND_CHOICES = [
        (KIND_ACADEMIC, "Academic document"),
        (KIND_OTHER, "Other"),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=30, choices=KIND_CHOICES, default=KIND_ACADEMIC)
    label = models.CharField(max_length=200, blank=True)
    file = models.FileField(upload_to="application_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        name = (self.label or "").strip() or self.file.name
        return f"{self.application_id}: {name}"


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")

    preferred_country = models.CharField(max_length=100, blank=True)
    preferred_level = models.CharField(max_length=30, choices=Scholarship.LEVEL_CHOICES, blank=True, default="")
    course = models.CharField(max_length=200, blank=True)
    qualifications = models.TextField(blank=True)

    cv = models.FileField(upload_to="profile_cvs/", blank=True, null=True)
    notify_new_scholarships = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile({self.user_id})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Notif({self.user_id}): {self.title}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} - {self.email}"
