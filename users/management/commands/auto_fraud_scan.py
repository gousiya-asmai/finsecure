from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.utils import analyze_and_notify_fraud

class Command(BaseCommand):
    help = "Automatically fetch Gmail transactions, detect fraud, and send alert emails."

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting automatic fraud detection...")
        for user in User.objects.all():
            if not user.email:
                continue
            try:
                result = analyze_and_notify_fraud(user)
                self.stdout.write(f"✅ {user.username}: {result}")
            except Exception as e:
                self.stdout.write(f"❌ Error for {user.username}: {e}")
        self.stdout.write("🏁 Automatic fraud scan completed.")
