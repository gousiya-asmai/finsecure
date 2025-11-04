from django.contrib.auth.models import User
from users.utils import analyze_and_notify_fraud

def run_auto_fraud_scan():
    print("🕒 Running automatic fraud scan (cron)...")
    for user in User.objects.all():
        try:
            analyze_and_notify_fraud(user)
        except Exception as e:
            print(f"❌ Error for {user.username}: {e}")
    print("✅ Fraud scan complete.")
