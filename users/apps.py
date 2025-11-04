from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"

    def ready(self):
        """
        Runs after all Django apps are loaded and migrations are ready.
        Perfect moment to register the Gmail auto-update scheduler.
        """
        try:
            # Import inside ready() to avoid premature Django setup
            from django.conf import settings
            from users.tasks import ensure_auto_scheduler

            q_cluster = getattr(settings, "Q_CLUSTER", {})  # safer than Conf.Q_CLUSTER

            # Avoid creating duplicate schedules when Q runs in sync/debug mode
            if not q_cluster.get("sync", False):
                ensure_auto_scheduler()

        except Exception as e:
            logger.error(f"❌ Failed to initialize Gmail auto scheduler: {e}", exc_info=True)
