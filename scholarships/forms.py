from django import forms
from django.contrib.auth import get_user_model

from .models import Scholarship
from .models import Application


class MultiFileInput(forms.ClearableFileInput):
    # Django's default file input is single-file; this enables <input multiple>.
    allow_multiple_selected = True


class ApplicationForm(forms.ModelForm):
    academic_documents = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={"class": "form-control", "multiple": True}),
        help_text="Upload transcripts/certificates/recommendation letters (optional).",
    )

    class Meta:
        model = Application
        fields = ["student_name", "email", "phone", "cv", "picture", "motivation_letter"]
        widgets = {
            "student_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "cv": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "picture": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "motivation_letter": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }


class ScholarshipForm(forms.ModelForm):
    class Meta:
        model = Scholarship
        # Use amount_display as "Amount" so admins can enter values like "Full Scholarship" or "KES 150,000 per year".
        fields = [
            "title",
            "organization",
            "country",
            "level",
            "category",
            "amount_display",
            "deadline",
            "requirements",
            "description",
            "image",
        ]
        labels = {
            "amount_display": "Amount",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "organization": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. UK, Canada, Germany"}),
            "level": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount_display": forms.TextInput(attrs={"class": "form-control"}),
            "deadline": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "requirements": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


User = get_user_model()


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class StudentProfileForm(forms.ModelForm):
    class Meta:
        from .models import StudentProfile  # avoid circular import issues in some environments

        model = StudentProfile
        fields = [
            "preferred_country",
            "preferred_level",
            "course",
            "qualifications",
            "cv",
            "notify_new_scholarships",
        ]
        widgets = {
            "preferred_country": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. UK, Canada"}),
            "preferred_level": forms.Select(attrs={"class": "form-select"}),
            "course": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Computer Science"}),
            "qualifications": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "cv": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
