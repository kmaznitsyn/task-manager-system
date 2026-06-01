import base64
import json
import logging
import os

import functions_framework

from cf_keycloak import get_user_email
from notifier import send_notification

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)


SUBJECTS = {
    "task.created": "New task created",
    "task.completed": "Your task is done",
}


@functions_framework.cloud_event
def handle_task_event(cloud_event):
    """
    Triggered by a Pub/Sub message from the task-service.
    Expected payload (base64-encoded inside the CloudEvent envelope):
      {"type": "task.created" | "task.completed",
       "task_id": "<uuid>",
       "owner_sub": "<keycloak-sub>"}
    """
    try:
        raw = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
        payload = json.loads(raw)
    except Exception:
        log.exception("failed to decode pubsub message")
        return  # ack — bad messages should not be retried indefinitely

    event_type = payload.get("type")
    task_id = payload.get("task_id")
    owner_sub = payload.get("owner_sub")
    if not event_type or not task_id or not owner_sub:
        log.warning("ignoring malformed event: %s", payload)
        return

    log.info("received %s for task %s owner %s", event_type, task_id, owner_sub)

    try:
        email = get_user_email(owner_sub)
    except Exception:
        log.exception("keycloak lookup failed for %s — will retry", owner_sub)
        # Re-raise → functions-framework returns 500 → Pub/Sub retries.
        raise

    if not email:
        log.warning("no email for user %s — skipping", owner_sub)
        return

    subject = SUBJECTS.get(event_type, f"Task update ({event_type})")
    html = f"<p>Task <code>{task_id}</code>: {event_type}.</p>"

    try:
        send_notification(email, subject=subject, html=html)
    except Exception:
        log.exception("send_notification failed — will retry")
        raise
