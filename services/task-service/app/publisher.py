import logging
import os
from functools import lru_cache

from google.cloud import pubsub_v1

from app.config import settings
from app.schemas import TaskEvent

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """Publish only if the emulator is configured or it's explicitly enabled.

    In local dev nobody has GCP credentials and we don't want a real Pub/Sub
    call to crash startup or block requests — so by default we just log.
    Set PUBSUB_EMULATOR_HOST to use the emulator, or PUBSUB_ENABLED=1 to
    publish to real Pub/Sub (e.g. in deployed environments).
    """
    return bool(os.environ.get("PUBSUB_EMULATOR_HOST")) or settings.pubsub_enabled


@lru_cache
def _topic() -> tuple[pubsub_v1.PublisherClient, str]:
    client = pubsub_v1.PublisherClient()
    path = client.topic_path(
        settings.pubsub_project_id, settings.pubsub_topic_tasks_events
    )
    return client, path


# TODO make async and more performant
def publish_task_event(event: TaskEvent) -> None:
    if not _enabled():
        logger.info(
            "pubsub disabled — would publish %s for task %s",
            event.type,
            event.task_id,
        )
        return

    client, path = _topic()
    future = client.publish(path, event.model_dump_json().encode("utf-8"))
    message_id = future.result(timeout=10)
    logger.info(
        "published %s for task %s as %s", event.type, event.task_id, message_id
    )
