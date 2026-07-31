from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings

from .models import DeviceToken

logger = logging.getLogger(__name__)


def _stringify_data(data: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """FCM data payloads must be flat string->string maps."""
    out: Dict[str, str] = {}
    for key, value in (data or {}).items():
        if value is None:
            continue
        if isinstance(value, str):
            out[str(key)] = value
        elif isinstance(value, (dict, list)):
            out[str(key)] = json.dumps(value)
        else:
            out[str(key)] = str(value)
    return out


def send_push_to_user(
    *,
    user_id: int,
    title: str,
    body: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> int:
    """Send an FCM push to every active device of a user.

    Returns the number of messages successfully delivered. Never raises:
    push delivery must never break the chat flow.
    """
    if not getattr(settings, 'PUSH_NOTIFICATIONS_ENABLED', True):
        return 0

    tokens: List[str] = list(
        DeviceToken.objects.filter(user_id=user_id, is_active=True)
        .values_list('token', flat=True)
    )
    if not tokens:
        return 0

    try:
        from firebase_admin import messaging
        from authentication.firebase import get_firebase_app

        app = get_firebase_app()
    except Exception:
        logger.exception('FCM is not configured; skipping push for user_id=%s', user_id)
        return 0

    payload = _stringify_data(data)
    # Lets the client route the tap to the right chat screen.
    payload.setdefault('click_action', 'FLUTTER_NOTIFICATION_CLICK')

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body or ''),
        data=payload,
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                sound='default',
                channel_id=getattr(settings, 'FCM_ANDROID_CHANNEL_ID', 'chat_messages'),
            ),
        ),
        apns=messaging.APNSConfig(
            headers={'apns-priority': '10', 'apns-push-type': 'alert'},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound='default', content_available=True),
            ),
        ),
    )

    try:
        response = messaging.send_each_for_multicast(message, app=app)
    except Exception:
        logger.exception('Failed to send FCM push for user_id=%s', user_id)
        return 0

    # Deactivate tokens FCM told us are dead, so we stop retrying them.
    stale: List[str] = []
    for token, result in zip(tokens, response.responses):
        if result.success:
            continue
        exc = result.exception
        code = getattr(exc, 'code', '') or ''
        if 'not-found' in str(code) or 'invalid-argument' in str(code) or 'unregistered' in str(code).lower():
            stale.append(token)

    if stale:
        DeviceToken.objects.filter(token__in=stale).update(is_active=False)

    return int(response.success_count)