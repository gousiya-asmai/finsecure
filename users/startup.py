import logging
from django_q.models import Schedule
from django.utils import timezone

logger = logging.getLogger(__name__)

def ensure_auto_scheduler():
    """
    Create or fix Gmail auto-update scheduler safely.
    """
    func_path = "users.tasks.auto_update_gmail_and_detect"

    job, created = Schedule.objects.get_or_create(
        name="gmail_auto_update",
        defaults={
            "func": func_path,
            "schedule_type": Schedule.MINUTES,
            "minutes": 2,
            "repeats": -1,
            "next_run": timezone.now(),
        },
    )

    if created:
        logger.info("✅ Created Gmail auto-update scheduler.")
    else:
        if job.func != func_path:
            job.func = func_path
            job.save()
            logger.info("🔄 Fixed Gmail auto-update func path.")
        else:
            logger.info("✅ Gmail auto-detect scheduler already active.")
