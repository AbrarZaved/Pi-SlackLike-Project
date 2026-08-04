from __future__ import annotations

import logging
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


def _notify_many(users: Iterable, *, notification_type: str, title: str, body: str, data: dict) -> int:
	from Notification.services import create_notification_for_user

	sent = 0
	for user in users:
		try:
			create_notification_for_user(
				user=user,
				notification_type=notification_type,
				title=title,
				body=body,
				data=data,
			)
			sent += 1
		except Exception:
			logger.exception('Failed to notify %s for %s', getattr(user, 'id', None), notification_type)
	return sent


def notify_workspace_status(*, workspace, is_active: bool, actor_id: Optional[int] = None) -> int:
	from authentication.models import User

	member_ids = set(workspace.users.values_list('id', flat=True))
	if workspace.user_id:
		member_ids.add(workspace.user_id)
	member_ids.discard(actor_id)

	return _notify_many(
		User.objects.filter(id__in=member_ids, is_active=True),
		notification_type='workspace.activated' if is_active else 'workspace.deactivated',
		title='Workspace reactivated' if is_active else 'Workspace deactivated',
		body=workspace.name,
		data={'workspace_id': workspace.id, 'is_active': is_active, 'actor_id': actor_id},
	)


def notify_channel_status(*, channel, is_active: bool, actor_id: Optional[int] = None) -> int:
	from authentication.models import User

	member_ids = set(channel.users.values_list('id', flat=True))
	if channel.user_id:
		member_ids.add(channel.user_id)
	member_ids.discard(actor_id)

	return _notify_many(
		User.objects.filter(id__in=member_ids, is_active=True),
		notification_type='channel.activated' if is_active else 'channel.deactivated',
		title='Channel reactivated' if is_active else 'Channel deactivated',
		body=channel.name,
		data={'channel_id': channel.id, 'is_active': is_active, 'actor_id': actor_id},
	)


def notify_group_status(*, group, is_active: bool, actor_id: Optional[int] = None) -> int:
	from authentication.models import User

	member_ids = set(group.users.values_list('id', flat=True))
	for owner_id in (group.group_admin_id, group.user_id):
		if owner_id:
			member_ids.add(owner_id)
	member_ids.discard(actor_id)

	return _notify_many(
		User.objects.filter(id__in=member_ids, is_active=True),
		notification_type='group.activated' if is_active else 'group.deactivated',
		title='Group reactivated' if is_active else 'Group deactivated',
		body=group.name,
		data={'group_id': group.id, 'is_active': is_active, 'actor_id': actor_id},
	)