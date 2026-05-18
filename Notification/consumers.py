from __future__ import annotations

from typing import Any, Dict, List

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from authentication.models import User

from .models import Notification


HISTORY_LIMIT = 50


class NotificationsConsumer(AsyncJsonWebsocketConsumer):
	"""Real-time notification stream for the authenticated user."""

	async def connect(self):
		user = self.scope.get('user')
		if not user or not user.is_authenticated:
			await self.close(code=4401)
			return

		self.user_id = int(user.id)
		self.group_name = f"notifications_user_{self.user_id}"

		await self.channel_layer.group_add(self.group_name, self.channel_name)
		await self.accept()

		items, unread_count = await self._get_latest_and_unread_count(user_id=self.user_id)
		await self.send_json({'type': 'notifications.init', 'unread_count': unread_count, 'items': items})

	async def disconnect(self, close_code):
		if getattr(self, 'group_name', None):
			await self.channel_layer.group_discard(self.group_name, self.channel_name)

	async def receive_json(self, content: Dict[str, Any], **kwargs):
		# Keep protocol minimal; reading is handled via REST endpoint.
		await self.send_json({'type': 'error', 'message': 'Unsupported event type'})

	async def notify_event(self, event: Dict[str, Any]):
		await self.send_json(event['payload'])

	@database_sync_to_async
	def _get_latest_and_unread_count(self, *, user_id: int) -> tuple[List[Dict[str, Any]], int]:
		qs = Notification.objects.filter(user_id=user_id).order_by('-created_at')[:HISTORY_LIMIT]
		items = [
			{
				'id': n.id,
				'notification_type': n.notification_type,
				'title': n.title,
				'body': n.body,
				'data': n.data,
				'is_read': n.is_read,
				'read_at': n.read_at.isoformat() if n.read_at else None,
				'created_at': n.created_at.isoformat(),
			}
			for n in reversed(list(qs))
		]
		unread = Notification.objects.filter(user_id=user_id, is_read=False).count()
		return items, int(unread)
