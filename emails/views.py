from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .utils import gmail_authenticate

@login_required
def connect_gmail(request):
    service = gmail_authenticate(request.user)
    return redirect("dashboard")  # After success, send user back to dashboard


# Create your views here.
