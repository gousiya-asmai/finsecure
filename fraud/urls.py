# fraud/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.fraud_home, name='fraud_home'),
]
