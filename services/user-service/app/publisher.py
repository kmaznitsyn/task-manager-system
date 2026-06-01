import json
import logging
import os
from functools import lru_cache

from google.cloud import pubsub_v1

from app.config import settings

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
def _client() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()


# TODO make async and more performant
def publish(topic: str, payload: dict) -> None:
    """Publish a payload to the named topic, blocking until Pub/Sub acks.

    Called by the outbox flush, which only marks a row published once this
    returns — so it must await the real ack (future.result), not fire-and-forget.
    """
    if not _enabled():
        logger.info("pubsub disabled — would publish to %s: %s", topic, payload)
        return

    client = _client()
    path = client.topic_path(settings.pubsub_project_id, topic)
    future = client.publish(path, json.dumps(payload).encode("utf-8"))
    message_id = future.result(timeout=10)
    logger.info("published to %s as %s", topic, message_id)
