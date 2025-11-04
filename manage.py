#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import dotenv
import subprocess
import threading
import time

dotenv.load_dotenv()


def start_auto_recycler():
    """
    Start Django Q cluster auto-recycler in background (every 5 seconds).
    Only runs when using 'runserver'.
    """
    try:
        def run_recycler():
            while True:
                print("♻️ Restarting Django Q cluster (auto, every 5s)...")
                process = subprocess.Popen(
                    ["python", "manage.py", "qcluster"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                )
                time.sleep(5)
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

        thread = threading.Thread(target=run_recycler, daemon=True)
        thread.start()
        print("🚀 Django Q auto-recycler started (5s interval).")
    except Exception as e:
        print(f"⚠️ Failed to start auto-recycler: {e}")


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # 🚀 Automatically start cluster recycler only when running the dev server
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        start_auto_recycler()

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
