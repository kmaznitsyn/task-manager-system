import logging
import os
from functools import lru_cache

from google.cloud import pubsub_v1

from app.config import settings
from app.schemas import DocumentEvent

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """Publish only if the emulator is configured or it's explicitly enabled.

    Same opt-in semantics as task-service: by default we just log so local
    dev works without GCP credentials.
    """
    return bool(os.environ.get("PUBSUB_EMULATOR_HOST")) or settings.pubsub_enabled


@lru_cache
def _topic() -> tuple[pubsub_v1.PublisherClient, str]:
    client = pubsub_v1.PublisherClient()
    path = client.topic_path(
        settings.pubsub_project_id, settings.pubsub_topic_documents_events
    )
    return client, path


def publish_document_event(event: DocumentEvent) -> None:
    if not _enabled():
        logger.info(
            "pubsub disabled — would publish %s for document %s",
            event.type,
            event.document_id,
        )
        return

    client, path = _topic()
    future = client.publish(path, event.model_dump_json().encode("utf-8"))
    message_id = future.result(timeout=10)
    logger.info(
        "published %s for document %s as %s",
        event.type,
        event.document_id,
        message_id,
    )
