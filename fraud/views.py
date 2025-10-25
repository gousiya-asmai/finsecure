# fraud/views.py
from django.shortcuts import render

def fraud_home(request):
    """
    Fraud Detection home page.
    Later you can extend this to include form inputs,
    fraud-check ML model predictions, or recent suspicious activities.
    """
    return render(request, "fraud/home.html")
