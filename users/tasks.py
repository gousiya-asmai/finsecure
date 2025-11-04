import logging
from django.utils import timezone
from django_q.models import Schedule

logger = logging.getLogger(__name__)


def auto_update_gmail_and_detect():
    """
    Entry point for Django Q scheduler.

    This function is called automatically by the scheduler every few minutes.
    It dynamically imports and runs the Gmail + fraud detection cycle to avoid
    circular import issues.
    """
    try:
        from users.utils import run_auto_gmail_and_fraud_cycle
        logger.info("⏳ Starting auto Gmail + fraud detection cycle...")
        run_auto_gmail_and_fraud_cycle()
        logger.info("✅ Automatic Gmail + fraud detection cycle complete.")
    except Exception as e:
        logger.exception("❌ Error in auto_update_gmail_and_detect: %s", e)


def ensure_auto_scheduler():
    """
    Ensures that the Gmail auto-detect scheduler exists and is valid.
    The job runs every 2 minutes indefinitely.
    """
    try:
        job_name = "gmail_auto_update"
        func_path = "users.tasks.auto_update_gmail_and_detect"

        # Ensure only one job exists with this name
        job, created = Schedule.objects.get_or_create(
            name=job_name,
            defaults={
                "func": func_path,
                "schedule_type": Schedule.MINUTES,
                "minutes": 2,
                "repeats": -1,
                "next_run": timezone.now(),
            },
        )

        if created:
            logger.info("✅ Created new Gmail auto-update schedule.")
        else:
            # Repair broken or missing func paths
            if not job.func or job.func != func_path:
                old_func = job.func
                job.func = func_path
                job.save()
                logger.warning("🔄 Repaired Gmail auto-update func path (was %s)", old_func)
            else:
                logger.info("✅ Gmail auto-detect scheduler already active and valid.")

    except Exception as e:
        logger.exception("❌ Failed to ensure scheduler: %s", e)
