from django.http import HttpResponse

def home(request):
    return HttpResponse("<h1>Main Home - Financial Assistance & Fraud Detection System</h1>")
