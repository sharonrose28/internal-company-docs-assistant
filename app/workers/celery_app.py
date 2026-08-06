from celery import Celery
from celery.signals import setup_logging

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
celery_app = Celery(
    "company_docs",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=900,
    task_soft_time_limit=840,
)


@setup_logging.connect
def configure_worker_logging(**_: object) -> None:
    """Prevent Celery from replacing the application's JSON logging handlers."""
    configure_logging(settings.log_level)
