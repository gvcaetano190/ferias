import os
import time

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
application = get_wsgi_application()

from apps.scheduler.services import SchedulerService  # noqa: E402


if __name__ == "__main__":
    poll_seconds = int(os.getenv("SCHEDULER_POLL_SECONDS", "60"))
    SchedulerService().loop_forever(poll_seconds=poll_seconds)

