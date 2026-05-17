from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from shared.settings import Settings

settings = Settings()

celery_app = Celery(
    "autopost_worker",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=["app.autopost_tasks"],
)

celery_app.conf.update(
    timezone=settings.celery.timezone,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=270,
)

if settings.celery.enable_beat:
    celery_app.conf.beat_schedule = {
        "autopost-publish-due-linkedin-jobs-every-minute": {
            "task": "app.autopost_tasks.publish_due_linkedin_jobs",
            "schedule": crontab(),
        }
    }
