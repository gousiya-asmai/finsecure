# users/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from assistance import views as assistance_views


urlpatterns = [
    # --- Home ---
    path("", views.home, name="home"),

    # --- Authentication ---
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("verify_otp/", views.verify_otp_view, name="verify_otp"),
    path("resend_otp/", views.resend_otp_view, name="resend_otp"),
    path("logout/", views.logout_view, name="logout"),

    # --- Dashboard ---
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("assistance/", views.assistance_view, name="assistance"),
    path("fraud_check/", views.fraud_check_view, name="fraud_check"),

    # --- Gmail Integration ---
    path("connect_gmail/", views.connect_gmail, name="connect_gmail"),

    # --- Email update ---
    path("update_email/", views.update_email_view, name="update_email"),

    # --- Password change ---
    path(
        "password_change/",
        auth_views.PasswordChangeView.as_view(
            template_name="users/password_change.html"
        ),
        name="password_change",
    ),
    path(
        "password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="users/password_change_done.html"
        ),
        name="password_change_done",
    ),
     path("dashboard/", assistance_views.dashboard, name="dashboard"),
    path("dashboard-data/", views.get_dashboard_data, name="get_dashboard_data"),
    # In users/urls.py or assistance/urls.py (depending on your structure)
    path('fraud-alerts/', views.fraud_alerts, name='fraud_alerts'),
    path('reports/', views.reports, name='reports'),
    path('settings/', views.settings, name='settings'),

]
