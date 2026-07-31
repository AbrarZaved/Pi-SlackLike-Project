from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5, ignore_result=True)
def send_push_notification(
    self,
    user_id: int,
    title: str,
    body: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> int:
    """Deliver a push notification to all of a user's registered devices."""
    from .push import send_push_to_user

    try:
        return send_push_to_user(user_id=user_id, title=title, body=body, data=data)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception('Push task failed for user_id=%s', user_id)
        raise self.retry(exc=exc)