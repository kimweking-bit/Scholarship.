from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Application, ApplicationAttachment, Scholarship, StudentProfile


class AdminDashboardTests(TestCase):
    def test_requires_staff(self):
        resp = self.client.get(reverse("admin_dashboard"))
        assert resp.status_code == 302
        assert "/admin/login/" in resp["Location"]

    def test_staff_can_view(self):
        User = get_user_model()
        user = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(user)

        s = Scholarship.objects.create(title="Example Scholarship")
        Application.objects.create(
            scholarship=s,
            user=user,
            student_name="Alice Applicant",
            email="alice@example.com",
            phone="0700000000",
            motivation_letter="Test",
        )
        resp = self.client.get(reverse("admin_dashboard"))
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert "Alice Applicant" in body
        assert "Example Scholarship" in body

    def test_student_records_include_qualifications_and_documents(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        student = User.objects.create_user(username="learner", password="pass", email="learner@example.com")
        self.client.force_login(staff)

        scholarship = Scholarship.objects.create(title="Data Leaders Scholarship", organization="Global Institute")
        application = Application.objects.create(
            scholarship=scholarship,
            user=student,
            student_name="Lina Student",
            email="learner@example.com",
            phone="0700000000",
            motivation_letter="I want to study data science.",
            cv="cv/learner-resume.pdf",
        )
        StudentProfile.objects.create(
            user=student,
            preferred_country="Germany",
            course="Computer Science",
            qualifications="BSc in Computer Science\nPython certification",
            cv="profile_cvs/learner-profile-cv.pdf",
        )
        ApplicationAttachment.objects.create(
            application=application,
            label="Transcript.pdf",
            file="application_docs/transcript.pdf",
        )

        resp = self.client.get(reverse("admin_dashboard"))
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert "Student Records and Documents" in body
        assert "Computer Science" in body
        assert "BSc in Computer Science" in body
        assert "Profile CV" in body
        assert "Transcript.pdf" in body


class LoginRedirectTests(TestCase):
    def test_staff_login_redirects_to_admin_dashboard(self):
        User = get_user_model()
        User.objects.create_user(username="staff", password="pass", is_staff=True)

        resp = self.client.post(
            reverse("login"),
            data={"username": "staff", "password": "pass"},
        )

        assert resp.status_code == 302
        assert resp["Location"] == reverse("admin_dashboard")

    def test_student_login_redirects_to_student_dashboard(self):
        User = get_user_model()
        User.objects.create_user(username="student", password="pass")

        resp = self.client.post(
            reverse("login"),
            data={"username": "student", "password": "pass"},
        )

        assert resp.status_code == 302
        assert resp["Location"] == reverse("student_dashboard")


class HomePageTests(TestCase):
    def test_homepage_renders_for_logged_out_user(self):
        resp = self.client.get(reverse("home"))
        assert resp.status_code == 200
        assert "index.html" in [template.name for template in resp.templates if template.name]

    def test_homepage_renders_for_logged_in_staff_user(self):
        User = get_user_model()
        user = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(user)

        resp = self.client.get(reverse("home"))
        assert resp.status_code == 200
        assert "index.html" in [template.name for template in resp.templates if template.name]

    def test_homepage_renders_for_logged_in_student_user(self):
        User = get_user_model()
        user = User.objects.create_user(username="student", password="pass")
        self.client.force_login(user)

        resp = self.client.get(reverse("home"))
        assert resp.status_code == 200
        assert "index.html" in [template.name for template in resp.templates if template.name]


class StudentDashboardTests(TestCase):
    def test_requires_login(self):
        resp = self.client.get(reverse("student_dashboard"), follow=True)
        assert resp.redirect_chain
        assert resp.redirect_chain[-1][0].startswith(reverse("login"))
        assert resp.status_code == 200

    def test_logged_in_can_view(self):
        User = get_user_model()
        user = User.objects.create_user(username="student", password="pass")
        self.client.force_login(user)

        Scholarship.objects.create(title="Example")
        resp = self.client.get(reverse("student_dashboard"))
        assert resp.status_code == 200


class ApplyScholarshipTests(TestCase):
    def test_requires_login(self):
        s = Scholarship.objects.create(title="Example")
        resp = self.client.get(reverse("apply_scholarship", args=[s.id]), follow=True)
        assert resp.redirect_chain
        assert resp.redirect_chain[-1][0].startswith(reverse("login"))
        assert resp.status_code == 200

    def test_get_ok_when_logged_in(self):
        User = get_user_model()
        user = User.objects.create_user(username="student", password="pass")
        self.client.force_login(user)
        s = Scholarship.objects.create(title="Example")

        resp = self.client.get(reverse("apply_scholarship", args=[s.id]))
        assert resp.status_code == 200

    def test_post_creates_application(self):
        User = get_user_model()
        user = User.objects.create_user(username="student", password="pass", email="student@example.com")
        self.client.force_login(user)
        s = Scholarship.objects.create(title="Example")

        resp = self.client.post(
            reverse("apply_scholarship", args=[s.id]),
            data={
                "student_name": "Student Name",
                "email": "",
                "phone": "0700000000",
                "motivation_letter": "I would like to apply.",
            },
        )
        assert resp.status_code == 302
        assert Application.objects.count() == 1
        app = Application.objects.get()
        assert app.scholarship_id == s.id
        assert app.user_id == user.id
        assert app.email == "student@example.com"


class ApproveRejectApplicationTests(TestCase):
    def test_requires_staff(self):
        User = get_user_model()
        user = User.objects.create_user(username="student", password="pass")
        s = Scholarship.objects.create(title="Example Scholarship")
        app = Application.objects.create(scholarship=s, user=user, student_name="A", email="a@b.com")

        resp = self.client.post(reverse("approve_application", args=[app.id]))
        assert resp.status_code == 302
        assert "/admin/login/" in resp["Location"]

    def test_approve_and_reject_are_post_only(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(staff)
        s = Scholarship.objects.create(title="Example Scholarship")
        app = Application.objects.create(scholarship=s, user=staff, student_name="A", email="a@b.com")

        resp = self.client.get(reverse("approve_application", args=[app.id]))
        assert resp.status_code == 405

        resp = self.client.get(reverse("reject_application", args=[app.id]))
        assert resp.status_code == 405

    def test_approve_updates_status(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(staff)
        s = Scholarship.objects.create(title="Example Scholarship")
        app = Application.objects.create(scholarship=s, user=staff, student_name="A", email="a@b.com")

        resp = self.client.post(reverse("approve_application", args=[app.id]))
        assert resp.status_code == 302
        app.refresh_from_db()
        assert app.status == Application.STATUS_APPROVED

    def test_reject_updates_status(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(staff)
        s = Scholarship.objects.create(title="Example Scholarship")
        app = Application.objects.create(scholarship=s, user=staff, student_name="A", email="a@b.com")

        resp = self.client.post(reverse("reject_application", args=[app.id]))
        assert resp.status_code == 302
        app.refresh_from_db()
        assert app.status == Application.STATUS_REJECTED


class CreateScholarshipTests(TestCase):
    def test_requires_staff(self):
        resp = self.client.get(reverse("create_scholarship"))
        assert resp.status_code == 302
        assert "/admin/login/" in resp["Location"]

    def test_staff_can_create(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(staff)

        resp = self.client.post(
            reverse("create_scholarship"),
            data={
                "title": "New Scholarship",
                "organization": "Org",
                "amount_display": "Full Scholarship",
                "deadline": "2026-08-30",
                "requirements": "Req",
                "description": "Desc",
            },
        )
        assert resp.status_code == 302
        assert Scholarship.objects.filter(title="New Scholarship").exists()


class DeleteScholarshipTests(TestCase):
    def test_requires_staff(self):
        s = Scholarship.objects.create(title="To Delete")
        resp = self.client.post(reverse("delete_scholarship", args=[s.id]))
        assert resp.status_code == 302
        assert "/admin/login/" in resp["Location"]
        assert Scholarship.objects.filter(id=s.id).exists()

    def test_post_only(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(staff)
        s = Scholarship.objects.create(title="To Delete")

        resp = self.client.get(reverse("delete_scholarship", args=[s.id]))
        assert resp.status_code == 405
        assert Scholarship.objects.filter(id=s.id).exists()

    def test_staff_can_delete(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.client.force_login(staff)
        s = Scholarship.objects.create(title="To Delete")

        resp = self.client.post(reverse("delete_scholarship", args=[s.id]))
        assert resp.status_code == 302
        assert not Scholarship.objects.filter(id=s.id).exists()
