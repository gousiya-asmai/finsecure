import time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.utils import analyze_and_notify_fraud

class Command(BaseCommand):
    help = "Continuously runs fraud detection every second (local dev only!)"

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting continuous fraud watcher (1-second interval)...")
        while True:
            for user in User.objects.all():
                try:
                    analyze_and_notify_fraud(user)
                except Exception as e:
                    self.stdout.write(f"❌ Error for {user.username}: {e}")
            self.stdout.write("✅ Scan cycle complete. Waiting 1 second...\n")
            time.sleep(1)
