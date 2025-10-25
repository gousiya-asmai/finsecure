# assistance/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Default URL: /assistance/
    path('', views.assist_home, name='assist_home'),

    # Optional alias: /assistance/home/
    path('home/', views.assist_home, name='assist_home_home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('connect-gmail/', views.connect_gmail, name='connect_gmail'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
    path("all-suggestions/", views.all_suggestions, name="all_suggestions"),
    
]
