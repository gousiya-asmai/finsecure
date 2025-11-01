"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from users import views as user_views
from transactions import views as transaction_views

# ✅ Add for serving media files in development
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
 # if your view is in the 'users' app


urlpatterns = [
    # --- Admin ---
    path("admin/", admin.site.urls),

    # --- Home (landing page) ---
    path("", user_views.home, name="home"),

    # --- App Routes ---
    path("users/", include("users.urls")),
    path("assistance/", include("assistance.urls")),
    path("transactions/", include("transactions.urls")),
    path("dashboard-data/", transaction_views.dashboard_data, name="dashboard_data"),
    path("auth/", include("social_django.urls", namespace="social")),
    path('googlee94c7ab361fbc045.html', TemplateView.as_view(template_name="googlee94c7ab361fbc045.html")),
]



# ✅ Serve media files (profile photos etc.) only in development

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
