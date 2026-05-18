from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from authentication.models import User

from .models import Notification, NotificationPreference, SystemSettings


def _get_system_settings() -> SystemSettings:
	obj, _ = SystemSettings.objects.get_or_create(id=1)
	return obj


def _user_allows_push(*, user: User) -> bool:
	settings_obj = _get_system_settings()
	if not settings_obj.push_notifications_enabled:
		return False
	prefs, _ = NotificationPreference.objects.get_or_create(user=user)
	return bool(prefs.push_mobile_notifications)


def _broadcast_to_user(*, user_id: int, payload: Dict[str, Any]) -> None:
	channel_layer = get_channel_layer()
	if channel_layer is None:
		return
	async_to_sync(channel_layer.group_send)(
		f"notifications_user_{user_id}",
		{'type': 'notify.event', 'payload': payload},
	)


@transaction.atomic
def create_notification_for_user(
	*,
	user: User,
	notification_type: str,
	title: str,
	body: Optional[str] = None,
	data: Optional[Dict[str, Any]] = None,
	target_role_slug: Optional[str] = None,
	broadcast: bool = True,
) -> Optional[Notification]:
	"""Create a notification row and optionally broadcast it via websocket.

	If push notifications are disabled globally or for the user, this returns None
	and no notification is stored.
	"""
	if not _user_allows_push(user=user):
		return None

	notification = Notification.objects.create(
		user=user,
		notification_type=notification_type,
		title=title,
		body=body,
		data=data or {},
		target_role_slug=target_role_slug,
	)

	if broadcast:
		_broadcast_to_user(
			user_id=user.id,
			payload={
				'type': 'notification.new',
				'notification': {
					'id': notification.id,
					'notification_type': notification.notification_type,
					'title': notification.title,
					'body': notification.body,
					'data': notification.data,
					'is_read': notification.is_read,
					'read_at': notification.read_at,
					'created_at': notification.created_at.isoformat(),
				},
			},
		)

	return notification


@transaction.atomic
def create_notifications_for_role(
	*,
	role_slug: str,
	notification_type: str,
	title: str,
	body: Optional[str] = None,
	data: Optional[Dict[str, Any]] = None,
	broadcast: bool = True,
) -> List[Notification]:
	"""Create notifications for all users with a given role.

	Only creates notifications for users who currently allow push notifications.
	"""
	users = User.objects.filter(role__slug=role_slug, is_active=True)
	created: List[Notification] = []

	for user in users:
		n = create_notification_for_user(
			user=user,
			notification_type=notification_type,
			title=title,
			body=body,
			data=data,
			target_role_slug=role_slug,
			broadcast=broadcast,
		)
		if n is not None:
			created.append(n)

	return created


def mark_all_as_read(*, user: User) -> int:
	"""Mark all unread notifications as read for the user."""
	now = timezone.now()
	updated = (
		Notification.objects.filter(user=user, is_read=False)
		.update(is_read=True, read_at=now)
	)
	return int(updated)
