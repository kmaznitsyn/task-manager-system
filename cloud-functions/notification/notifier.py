"""Email delivery via SendGrid, with a log-only fallback for local dev.

If SENDGRID_API_KEY isn't set we log the would-be email rather than
raising — the function should still be runnable locally without a
SendGrid account.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL = os.environ.get("NOTIFICATION_FROM_EMAIL", "no-reply@taskmanager.local")


def send_notification(to_email: str, subject: str, html: str) -> None:
    if not SENDGRID_API_KEY:
        logger.info(
            "SENDGRID_API_KEY not set — would send to %s subject=%r", to_email, subject
        )
        return

    # Imported lazily so unit tests / log-only mode don't need the dep.
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    msg = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html,
    )
    resp = SendGridAPIClient(SENDGRID_API_KEY).send(msg)
    if resp.status_code >= 300:
        raise RuntimeError(f"SendGrid {resp.status_code}: {resp.body!r}")
    logger.info("sent notification to %s (sendgrid %s)", to_email, resp.status_code)
