from __future__ import annotations

from app.autopost_celery import celery_app
from app.services.autopost_service import (
    AutopostService,
    ProcessAutopostJobInput,
    ReconcileAutopostJobInput,
)
from shared.settings import Settings


@celery_app.task(
    name="app.autopost_tasks.process_autopost_job", bind=True, max_retries=3
)
def process_autopost_job(self, job_id: str):
    service = AutopostService()
    result = service.process_job(ProcessAutopostJobInput(job_id=job_id))
    if not result.status and result.code >= 500:
        raise self.retry(countdown=30)
    return result.model_dump(mode="json")


@celery_app.task(
    name="app.autopost_tasks.publish_due_linkedin_jobs",
    bind=True,
    max_retries=1,
)
def publish_due_linkedin_jobs(self):
    service = AutopostService()
    limit = Settings().celery.due_scan_limit
    result = service.publish_due_linkedin_jobs(limit=limit)
    if not result.status and result.code >= 500:
        raise self.retry(countdown=20)
    return result.model_dump(mode="json")


@celery_app.task(
    name="app.autopost_tasks.reconcile_autopost_job",
    bind=True,
    max_retries=1,
)
def reconcile_autopost_job(self, job_id: str):
    service = AutopostService()
    result = service.reconcile_publish_unknown(
        ReconcileAutopostJobInput(job_id=job_id)
    )
    if not result.status and result.code >= 500:
        raise self.retry(countdown=30)
    return result.model_dump(mode="json")
