from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional, Set

from .models import Call

logger = logging.getLogger(__name__)


def _display_name(user) -> str:
	return (
		(getattr(user, 'name', None) or '').strip()
		or (getattr(user, 'email', None) or '').strip()
		or 'Someone'
	)


def _call_data(call: Call) -> Dict[str, Any]:
	"""Payload the client needs to render / route an incoming call."""
	return {
		'call_id': str(call.id),
		'room_name': call.room_name,
		'context_type': call.context_type,
		'workspace_id': call.workspace_id,
		'channel_id': call.channel_id,
		'dm_thread_id': call.dm_thread_id,
		'is_video': call.is_video,
		'created_by_id': call.created_by_id,
		'title': call.title or '',
	}


def notify_call_invited(*, call: Call, exclude_user_ids: Iterable[int] = ()) -> int:
	"""Ring every invited participant except the caller. Never raises."""
	from Notification.services import create_notification_for_user

	skip: Set[int] = {int(i) for i in exclude_user_ids}
	caller_name = _display_name(call.created_by)
	kind = 'video call' if call.is_video else 'voice call'
	sent = 0

	participants = (
		call.participants.select_related('user')
		.exclude(user_id__in=skip)
		.filter(user__is_active=True)
	)

	for participant in participants:
		try:
			create_notification_for_user(
				user=participant.user,
				notification_type='call.incoming',
				title=f'Incoming {kind}',
				body=f'{caller_name} is calling you',
				data={**_call_data(call), 'event': 'incoming'},
			)
			sent += 1
		except Exception:
			logger.exception('Failed to notify call invite for call_id=%s user_id=%s', call.id, participant.user_id)

	return sent


def notify_call_finished(*, call: Call, ended_by_id: Optional[int] = None) -> int:
	"""After a call ends: 'missed call' for people who never joined,
	'call ended' for the ones who were in it. Never raises.
	"""
	from Notification.services import create_notification_for_user

	caller_name = _display_name(call.created_by)
	kind = 'video call' if call.is_video else 'voice call'

	duration_seconds = None
	if call.ended_at:
		duration_seconds = int((call.ended_at - call.started_at).total_seconds())

	sent = 0
	participants = call.participants.select_related('user').filter(user__is_active=True)

	for participant in participants:
		if participant.user_id == call.created_by_id:
			continue

		missed = participant.joined_at is None
		try:
			create_notification_for_user(
				user=participant.user,
				notification_type='call.missed' if missed else 'call.ended',
				title=f'Missed {kind}' if missed else f'{kind.capitalize()} ended',
				body=(
					f'You missed a {kind} from {caller_name}'
					if missed
					else f'Your {kind} with {caller_name} has ended'
				),
				data={
					**_call_data(call),
					'event': 'missed' if missed else 'ended',
					'ended_by_id': ended_by_id,
					'duration_seconds': duration_seconds,
				},
			)
			sent += 1
		except Exception:
			logger.exception('Failed to notify call end for call_id=%s user_id=%s', call.id, participant.user_id)

	return sent