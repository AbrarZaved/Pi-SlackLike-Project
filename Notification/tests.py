from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User, Role

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken

from Pi.asgi import application

from .models import Notification
from .services import create_notification_for_user


class NotificationPreferencesTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(email='prefs@example.com', password='password123')
		self.client.force_authenticate(user=self.user)

	def test_get_preferences_creates_default_row(self):
		url = reverse('notification-preferences')
		resp = self.client.get(url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertIn('email_direct_messages', resp.data)
		self.assertIn('email_mentions', resp.data)
		self.assertIn('push_mobile_notifications', resp.data)
		self.assertIn('push_sound_alerts', resp.data)

		# Thread replies is intentionally not supported
		self.assertNotIn('thread_replies', resp.data)

	def test_patch_preferences(self):
		url = reverse('notification-preferences')
		resp = self.client.patch(url, {'email_mentions': False, 'push_sound_alerts': False}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertFalse(resp.data['email_mentions'])
		self.assertFalse(resp.data['push_sound_alerts'])


class NotificationsApiTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(email='notifs@example.com', password='password123')
		self.client.force_authenticate(user=self.user)

	def test_list_and_mark_all_as_read(self):
		Notification.objects.create(
			user=self.user,
			notification_type='test',
			title='Hello',
			body='Body',
		)
		Notification.objects.create(
			user=self.user,
			notification_type='test',
			title='Hello2',
			body='Body2',
			is_read=True,
		)

		list_url = reverse('my-notifications')
		list_resp = self.client.get(list_url)
		self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(list_resp.data['unread_count'], 1)
		self.assertIn('notifications', list_resp.data)
		self.assertEqual(len(list_resp.data['notifications']), 2)

		mark_url = reverse('notifications-mark-all-read')
		mark_resp = self.client.post(mark_url)
		self.assertEqual(mark_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(mark_resp.data['marked_read'], 1)

		list_resp2 = self.client.get(list_url)
		self.assertEqual(list_resp2.data['unread_count'], 0)


class NotificationsWebsocketTests(APITestCase):
	def test_notifications_websocket_receives_new_notification(self):
		user = User.objects.create_user(email='ws-notifs@example.com', password='password123')
		token = str(AccessToken.for_user(user))

		async_to_sync(self._assert_ws_delivery)(token=token, user_id=user.id)

	async def _assert_ws_delivery(self, *, token: str, user_id: int):
		communicator = WebsocketCommunicator(application, f"/ws/notifications/?token={token}")
		connected, _ = await communicator.connect()
		self.assertTrue(connected)

		init = await communicator.receive_json_from()
		self.assertEqual(init.get('type'), 'notifications.init')

		# Create a notification and ensure it arrives as notification.new
		user = await database_sync_to_async(User.objects.get)(id=user_id)
		await database_sync_to_async(create_notification_for_user)(
			user=user,
			notification_type='test.ws',
			title='Ping',
			body='Pong',
			data={'k': 'v'},
		)

		event = await communicator.receive_json_from()
		self.assertEqual(event.get('type'), 'notification.new')
		self.assertEqual(event['notification']['title'], 'Ping')
		self.assertEqual(event['notification']['body'], 'Pong')

		await communicator.disconnect()


class AdminSystemSettingsTests(APITestCase):
	def setUp(self):
		self.admin_role = Role.objects.create(name='Admin', slug='admin')
		self.admin_user = User.objects.create_user(
			email='admin-settings@example.com',
			password='password123',
			role=self.admin_role,
		)
		self.normal_user = User.objects.create_user(email='user-settings@example.com', password='password123')

	def test_non_admin_forbidden(self):
		self.client.force_authenticate(user=self.normal_user)
		url = reverse('admin-system-settings')
		resp = self.client.get(url)
		self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

	def test_admin_can_get_and_patch(self):
		self.client.force_authenticate(user=self.admin_user)
		url = reverse('admin-system-settings')

		get_resp = self.client.get(url)
		self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
		self.assertIn('email_notifications_enabled', get_resp.data)
		self.assertIn('push_notifications_enabled', get_resp.data)
		self.assertIn('auto_reply_enabled', get_resp.data)
		self.assertIn('file_sharing_enabled', get_resp.data)
		self.assertIn('video_calls_enabled', get_resp.data)
		self.assertIn('screen_sharing_enabled', get_resp.data)

		patch_resp = self.client.patch(url, {'screen_sharing_enabled': False}, format='json')
		self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
		self.assertFalse(patch_resp.data['screen_sharing_enabled'])
