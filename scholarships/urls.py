from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("scholarships/", views.scholarships_list, name="scholarships"),
    path("about/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("contact/", views.contact, name="contact"),
    path("register/", views.register, name="register"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-scholarships/", views.admin_scholarships, name="admin_scholarships"),
    path("edit-scholarship/<int:id>/", views.edit_scholarship, name="edit_scholarship"),
    path("toggle-scholarship/<int:id>/", views.toggle_scholarship_active, name="toggle_scholarship_active"),
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
    path("profile/", views.profile, name="profile"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/mark-read/<int:id>/", views.notification_mark_read, name="notification_mark_read"),
    path("notifications/mark-all-read/", views.notifications_mark_all_read, name="notifications_mark_all_read"),
    path("my-applications/", views.my_applications, name="my_applications"),
    path("apply/<int:id>/", views.apply_scholarship, name="apply_scholarship"),
    path("approve/<int:id>/", views.approve_application, name="approve_application"),
    path("reject/<int:id>/", views.reject_application, name="reject_application"),
    path("create-scholarship/", views.create_scholarship, name="create_scholarship"),
    path("delete-scholarship/<int:id>/", views.delete_scholarship, name="delete_scholarship"),
]
