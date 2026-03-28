from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from authentication.models import User
from django.utils import timezone
from datetime import timedelta
from django.test import TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken

from Pi.asgi import application
from Admin.models import Automation
from Notification.models import Notification
from Notification.models import SystemSettings

from .models import Workspace, Channel, ChatMessage, ChatAttachment


def _ensure_admin_role():
	"""Create an Admin role if it doesn't exist (used by tests)."""
	from authentication.models import Role
	role, _ = Role.objects.get_or_create(
		slug='admin',
		defaults={
			'name': 'Admin',
			'description': 'Administrator with full access',
			'is_system_role': True,
		},
	)
	return role


class WorkspaceListSummaryTests(APITestCase):
	def setUp(self):
		admin_role = _ensure_admin_role()
		self.user = User.objects.create_user(
			email='test@example.com',
			password='password123',
			role=admin_role,
		)
		self.client.force_authenticate(user=self.user)

	def test_workspace_list_includes_total_active_inactive_counts(self):
		Workspace.objects.create(name='WS 1', is_active=True, user=self.user)
		Workspace.objects.create(name='WS 2', is_active=True, user=self.user)
		Workspace.objects.create(name='WS 3', is_active=False, user=self.user)

		url = reverse('workspace-list')
		response = self.client.get(url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('total_workspaces', response.data)
		self.assertIn('total_active_workspaces', response.data)
		self.assertIn('total_inactive_workspaces', response.data)
		self.assertIn('workspaces', response.data)

		self.assertEqual(response.data['total_workspaces'], 3)
		self.assertEqual(response.data['total_active_workspaces'], 2)
		self.assertEqual(response.data['total_inactive_workspaces'], 1)
		self.assertEqual(len(response.data['workspaces']), 3)

	def test_workspace_list_counts_respect_search_filter(self):
		Workspace.objects.create(name='Alpha', is_active=True, user=self.user)
		Workspace.objects.create(name='Alpha Two', is_active=False, user=self.user)
		Workspace.objects.create(name='Beta', is_active=False, user=self.user)

		url = reverse('workspace-list')
		response = self.client.get(url, {'search': 'alpha'})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['total_workspaces'], 2)
		self.assertEqual(response.data['total_active_workspaces'], 1)
		self.assertEqual(response.data['total_inactive_workspaces'], 1)
		self.assertEqual(len(response.data['workspaces']), 2)


class WorkspaceListNonAdminResponseTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(email='nonadmin@example.com', password='password123')
		self.client.force_authenticate(user=self.user)

	def test_workspace_list_hides_summary_fields_for_non_admin(self):
		Workspace.objects.create(name='WS 1', is_active=True, user=self.user)
		url = reverse('workspace-list')
		response = self.client.get(url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('workspaces', response.data)
		self.assertNotIn('total_workspaces', response.data)
		self.assertNotIn('total_active_workspaces', response.data)
		self.assertNotIn('total_inactive_workspaces', response.data)

	def test_workspace_list_only_returns_created_or_joined(self):
		created = Workspace.objects.create(name='Created', is_active=True, user=self.user)
		joined = Workspace.objects.create(name='Joined', is_active=True)
		joined.users.add(self.user)
		Workspace.objects.create(name='Other', is_active=True)

		url = reverse('workspace-list')
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)

		names = {ws['name'] for ws in response.data['workspaces']}
		self.assertEqual(names, {created.name, joined.name})


class IsActivePatchPermissionsTests(APITestCase):
	def setUp(self):
		admin_role = _ensure_admin_role()
		self.admin = User.objects.create_user(email='isactive-admin@example.com', password='password123', role=admin_role)
		self.owner = User.objects.create_user(email='isactive-owner@example.com', password='password123')
		self.other = User.objects.create_user(email='isactive-other@example.com', password='password123')

		self.workspace = Workspace.objects.create(name='WS Active', is_active=True, user=self.owner)
		self.channel = Channel.objects.create(name='CH Active', type='public', is_active=True, user=self.owner)

	def test_admin_can_patch_workspace_is_active(self):
		self.client.force_authenticate(user=self.admin)
		url = reverse('workspace-detail', kwargs={'pk': self.workspace.id})
		resp = self.client.patch(url, {'is_active': False}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.workspace.refresh_from_db()
		self.assertFalse(self.workspace.is_active)

	def test_non_owner_non_admin_cannot_patch_workspace(self):
		self.client.force_authenticate(user=self.other)
		url = reverse('workspace-detail', kwargs={'pk': self.workspace.id})
		resp = self.client.patch(url, {'is_active': False}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
		self.workspace.refresh_from_db()
		self.assertTrue(self.workspace.is_active)

	def test_admin_can_patch_channel_is_active(self):
		self.client.force_authenticate(user=self.admin)
		url = reverse('channel-detail', kwargs={'pk': self.channel.id})
		resp = self.client.patch(url, {'is_active': False}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.channel.refresh_from_db()
		self.assertFalse(self.channel.is_active)

	def test_non_owner_non_admin_cannot_patch_channel(self):
		self.client.force_authenticate(user=self.other)
		url = reverse('channel-detail', kwargs={'pk': self.channel.id})
		resp = self.client.patch(url, {'is_active': False}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
		self.channel.refresh_from_db()
		self.assertTrue(self.channel.is_active)


class ChannelListSummaryTests(APITestCase):
	def setUp(self):
		admin_role = _ensure_admin_role()
		self.user = User.objects.create_user(
			email='channels@example.com',
			password='password123',
			role=admin_role,
		)
		self.client.force_authenticate(user=self.user)

	def test_channel_list_includes_total_active_inactive_counts(self):
		ws = Workspace.objects.create(name='WS', user=self.user)
		c1 = Channel.objects.create(name='C1', type='public', is_active=True, user=self.user)
		c2 = Channel.objects.create(name='C2', type='private', is_active=False, user=self.user)
		c3 = Channel.objects.create(name='C3', type='public', is_active=True, user=self.user)
		ws.channels.add(c1, c2, c3)
		c1.users.add(self.user)
		c2.users.add(self.user)
		c3.users.add(self.user)

		# Messages: 2 today for c1, 1 yesterday for c2
		ChatMessage.objects.create(sender=self.user, channel=c1, content='m1')
		ChatMessage.objects.create(sender=self.user, channel=c1, content='m2')
		old_msg = ChatMessage.objects.create(sender=self.user, channel=c2, content='old')
		ChatMessage.objects.filter(id=old_msg.id).update(created_at=timezone.now() - timedelta(days=1))

		url = reverse('channel-list')
		response = self.client.get(url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('total_channels', response.data)
		self.assertIn('total_active_channels', response.data)
		self.assertIn('total_inactive_channels', response.data)
		self.assertIn('messages_today_count', response.data)
		self.assertIn('channels', response.data)

		self.assertEqual(response.data['total_channels'], 3)
		self.assertEqual(response.data['total_active_channels'], 2)
		self.assertEqual(response.data['total_inactive_channels'], 1)
		self.assertEqual(response.data['messages_today_count'], 2)
		self.assertEqual(len(response.data['channels']), 3)

		first = response.data['channels'][0]
		self.assertIn('workspaces', first)
		self.assertIn('messages_count', first)

	def test_channel_list_counts_respect_type_filter(self):
		ws = Workspace.objects.create(name='WS', user=self.user)
		pub = Channel.objects.create(name='Public 1', type='public', is_active=True, user=self.user)
		p1 = Channel.objects.create(name='Private 1', type='private', is_active=True, user=self.user)
		p2 = Channel.objects.create(name='Private 2', type='private', is_active=False, user=self.user)
		ws.channels.add(pub, p1, p2)
		pub.users.add(self.user)
		p1.users.add(self.user)
		p2.users.add(self.user)

		ChatMessage.objects.create(sender=self.user, channel=p1, content='today')

		url = reverse('channel-list')
		response = self.client.get(url, {'type': 'private'})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['total_channels'], 2)
		self.assertEqual(response.data['total_active_channels'], 1)
		self.assertEqual(response.data['total_inactive_channels'], 1)
		self.assertEqual(len(response.data['channels']), 2)

		# Both channels returned should include workspaces and messages_count
		for ch in response.data['channels']:
			self.assertIn('workspaces', ch)
			self.assertIn('messages_count', ch)


class ChannelListNonAdminResponseTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(email='channels-nonadmin@example.com', password='password123')
		self.client.force_authenticate(user=self.user)

	def test_channel_list_hides_summary_fields_for_non_admin(self):
		ws = Workspace.objects.create(name='WS', user=self.user)
		c1 = Channel.objects.create(name='C1', type='public', is_active=True, user=self.user)
		ws.channels.add(c1)
		c1.users.add(self.user)

		url = reverse('channel-list')
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('channels', response.data)
		self.assertNotIn('total_channels', response.data)
		self.assertNotIn('total_active_channels', response.data)
		self.assertNotIn('total_inactive_channels', response.data)
		self.assertNotIn('messages_today_count', response.data)

	def test_channel_list_only_returns_created_or_joined(self):
		ws = Workspace.objects.create(name='WS')
		created = Channel.objects.create(name='Created', type='public', is_active=True, user=self.user)
		joined = Channel.objects.create(name='Joined', type='public', is_active=True)
		other = Channel.objects.create(name='Other', type='public', is_active=True)
		ws.channels.add(created, joined, other)
		joined.users.add(self.user)

		url = reverse('channel-list')
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		returned_names = {ch['name'] for ch in response.data['channels']}
		self.assertEqual(returned_names, {created.name, joined.name})


class ChannelAddUsersWorkspaceMembershipGuardTests(APITestCase):
	def setUp(self):
		self.adder = User.objects.create_user(email='adder-guard@example.com', password='password123')
		self.target = User.objects.create_user(email='target-guard@example.com', password='password123')
		self.workspace = Workspace.objects.create(name='WS Guard', user=self.adder)
		self.channel = Channel.objects.create(name='C Guard', type='public', is_active=True, user=self.adder)
		self.workspace.channels.add(self.channel)
		self.workspace.users.add(self.adder)
		self.client.force_authenticate(user=self.adder)

	def test_cannot_add_user_to_channel_if_not_in_workspace(self):
		url = reverse('channel-add-users', args=[self.channel.id])
		resp = self.client.post(url, {'user_ids': [self.target.id]}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('missing_workspace_user_ids', resp.data)
		self.assertIn(self.target.id, resp.data['missing_workspace_user_ids'])
		self.assertFalse(self.channel.users.filter(id=self.target.id).exists())

	def test_can_add_user_after_adding_to_workspace(self):
		self.workspace.users.add(self.target)
		url = reverse('channel-add-users', args=[self.channel.id])
		resp = self.client.post(url, {'user_ids': [self.target.id]}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertTrue(self.channel.users.filter(id=self.target.id).exists())


class MembershipAddedNotificationWebsocketTests(TransactionTestCase):
	reset_sequences = True

	def setUp(self):
		# Ensure notification broadcasting is enabled for these tests
		SystemSettings.objects.update_or_create(id=1, defaults={'push_notifications_enabled': True})

	def test_notification_sent_when_user_added_to_workspace(self):
		adder = User.objects.create_user(email='adder-ws@example.com', password='password123')
		added = User.objects.create_user(email='added-ws@example.com', password='password123')
		workspace = Workspace.objects.create(name='WS', user=adder)

		token = str(AccessToken.for_user(added))
		async_to_sync(self._assert_workspace_add_notification)(
			token=token,
			adder_id=adder.id,
			added_id=added.id,
			workspace_id=workspace.id,
		)

	def test_notification_sent_when_user_added_to_channel(self):
		adder = User.objects.create_user(email='adder-ch@example.com', password='password123')
		added = User.objects.create_user(email='added-ch@example.com', password='password123')
		channel = Channel.objects.create(name='General', type='public', is_active=True, user=adder)

		token = str(AccessToken.for_user(added))
		async_to_sync(self._assert_channel_add_notification)(
			token=token,
			adder_id=adder.id,
			added_id=added.id,
			channel_id=channel.id,
		)

	def _post_add_users(self, *, adder_id: int, url: str, added_id: int) -> int:
		adder = User.objects.get(id=adder_id)
		client = APIClient()
		client.force_authenticate(user=adder)
		resp = client.post(url, {'user_ids': [added_id]}, format='json')
		return int(resp.status_code)

	async def _assert_workspace_add_notification(self, *, token: str, adder_id: int, added_id: int, workspace_id: int):
		communicator = WebsocketCommunicator(application, f"/ws/notifications/?token={token}")
		connected, _ = await communicator.connect()
		self.assertTrue(connected)

		init = await communicator.receive_json_from()
		self.assertEqual(init.get('type'), 'notifications.init')

		url = reverse('workspace-add-users', args=[workspace_id])
		status_code = await database_sync_to_async(self._post_add_users)(
			adder_id=adder_id,
			url=url,
			added_id=added_id,
		)
		self.assertEqual(status_code, status.HTTP_200_OK)

		event = await communicator.receive_json_from()
		self.assertEqual(event.get('type'), 'notification.new')
		self.assertEqual(event['notification']['notification_type'], 'workspace.added')

		await communicator.disconnect()

	async def _assert_channel_add_notification(self, *, token: str, adder_id: int, added_id: int, channel_id: int):
		communicator = WebsocketCommunicator(application, f"/ws/notifications/?token={token}")
		connected, _ = await communicator.connect()
		self.assertTrue(connected)

		init = await communicator.receive_json_from()
		self.assertEqual(init.get('type'), 'notifications.init')

		url = reverse('channel-add-users', args=[channel_id])
		status_code = await database_sync_to_async(self._post_add_users)(
			adder_id=adder_id,
			url=url,
			added_id=added_id,
		)
		self.assertEqual(status_code, status.HTTP_200_OK)

		event = await communicator.receive_json_from()
		self.assertEqual(event.get('type'), 'notification.new')
		self.assertEqual(event['notification']['notification_type'], 'channel.added')

		await communicator.disconnect()


class ChannelWelcomeAutomationWebsocketTests(TransactionTestCase):
	reset_sequences = True

	def test_welcome_automation_auto_replies_in_channel_chat(self):
		member = User.objects.create_user(email='member@example.com', password='password123')
		bot = User.objects.create_user(email='bot@example.com', password='password123')

		workspace = Workspace.objects.create(name='WS')
		channel = Channel.objects.create(name='General', type='public', is_active=True)
		workspace.channels.add(channel)
		channel.users.add(member)

		Automation.objects.create(
			name='Welcome automation',
			workspace=workspace,
			trigger_type=Automation.TRIGGER_NEW_MESSAGE,
			action_type=Automation.ACTION_SEND_MESSAGE,
			message_content='Welcome to the channel!',
			is_enabled=True,
			created_by=bot,
		)

		token = str(AccessToken.for_user(member))

		async_to_sync(self._assert_welcome_reply_over_ws)(
			token=token,
			channel_id=channel.id,
			member_id=member.id,
			bot_id=bot.id,
		)

	async def _assert_welcome_reply_over_ws(self, *, token: str, channel_id: int, member_id: int, bot_id: int):
		communicator = WebsocketCommunicator(
			application,
			f"/ws/chat/channels/{channel_id}/?token={token}",
		)
		connected, _ = await communicator.connect()
		self.assertTrue(connected)

		history = await communicator.receive_json_from()
		self.assertEqual(history.get('type'), 'history')
		self.assertEqual(history.get('items'), [])

		await communicator.send_json_to({'type': 'message.send', 'content': 'Hello'})

		first = await communicator.receive_json_from()
		self.assertEqual(first.get('type'), 'message.new')
		self.assertEqual(first['message']['content'], 'Hello')
		self.assertEqual(first['message']['sender']['id'], member_id)

		second = await communicator.receive_json_from()
		self.assertEqual(second.get('type'), 'message.new')
		self.assertEqual(second['message']['content'], 'Welcome to the channel!')
		self.assertEqual(second['message']['sender']['id'], bot_id)

		await communicator.disconnect()


class ChatNotificationSuppressionWebsocketTests(TransactionTestCase):
	reset_sequences = True

	def test_no_notification_when_recipient_connected_to_same_room(self):
		sender = User.objects.create_user(email='sender@example.com', password='password123')
		recipient = User.objects.create_user(email='recipient@example.com', password='password123')

		workspace = Workspace.objects.create(name='WS')
		channel = Channel.objects.create(name='General', type='public', is_active=True)
		workspace.channels.add(channel)
		channel.users.add(sender)
		channel.users.add(recipient)

		sender_token = str(AccessToken.for_user(sender))
		recipient_token = str(AccessToken.for_user(recipient))

		async_to_sync(self._assert_suppression)(
			sender_token=sender_token,
			recipient_token=recipient_token,
			channel_id=channel.id,
			recipient_id=recipient.id,
		)

	async def _assert_suppression(self, *, sender_token: str, recipient_token: str, channel_id: int, recipient_id: int):
		recipient_ws = WebsocketCommunicator(application, f"/ws/chat/channels/{channel_id}/?token={recipient_token}")
		sender_ws = WebsocketCommunicator(application, f"/ws/chat/channels/{channel_id}/?token={sender_token}")

		connected_r, _ = await recipient_ws.connect()
		self.assertTrue(connected_r)
		_ = await recipient_ws.receive_json_from()  # history

		connected_s, _ = await sender_ws.connect()
		self.assertTrue(connected_s)
		_ = await sender_ws.receive_json_from()  # history

		await sender_ws.send_json_to({'type': 'message.send', 'content': 'Hello'})
		_ = await sender_ws.receive_json_from()  # message.new
		_ = await recipient_ws.receive_json_from()  # message.new

		count_connected = await database_sync_to_async(Notification.objects.filter(user_id=recipient_id).count)()
		self.assertEqual(count_connected, 0)

		await recipient_ws.disconnect()

		await sender_ws.send_json_to({'type': 'message.send', 'content': 'Hello again'})
		_ = await sender_ws.receive_json_from()  # message.new

		count_disconnected = await database_sync_to_async(Notification.objects.filter(user_id=recipient_id).count)()
		self.assertEqual(count_disconnected, 1)

		await sender_ws.disconnect()


class DirectMessageNotificationWebsocketTests(TransactionTestCase):
	reset_sequences = True

	def test_dm_notification_sent_when_recipient_not_in_dm_chat(self):
		sender = User.objects.create_user(email='dm-sender@example.com', password='password123', name='Sender')
		recipient = User.objects.create_user(email='dm-recipient@example.com', password='password123', name='Recipient')

		sender_token = str(AccessToken.for_user(sender))
		recipient_token = str(AccessToken.for_user(recipient))

		async_to_sync(self._assert_dm_notification)(
			sender_token=sender_token,
			recipient_token=recipient_token,
			recipient_id=recipient.id,
		)

	async def _assert_dm_notification(self, *, sender_token: str, recipient_token: str, recipient_id: int):
		# Recipient listens on notifications websocket (not connected to DM chat)
		notify_ws = WebsocketCommunicator(application, f"/ws/notifications/?token={recipient_token}")
		connected_n, _ = await notify_ws.connect()
		self.assertTrue(connected_n)
		_ = await notify_ws.receive_json_from()  # notifications.init

		dm_ws = WebsocketCommunicator(application, f"/ws/chat/dm/{recipient_id}/?token={sender_token}")
		connected_d, _ = await dm_ws.connect()
		self.assertTrue(connected_d)
		_ = await dm_ws.receive_json_from()  # history

		await dm_ws.send_json_to({'type': 'message.send', 'content': 'Hi there'})
		_ = await dm_ws.receive_json_from()  # message.new

		event = await notify_ws.receive_json_from()
		self.assertEqual(event.get('type'), 'notification.new')
		self.assertEqual(event['notification']['notification_type'], 'chat.direct_message')
		self.assertEqual(event['notification']['title'], 'New message')

		count = await database_sync_to_async(Notification.objects.filter(user_id=recipient_id).count)()
		self.assertEqual(count, 1)

		await dm_ws.disconnect()
		await notify_ws.disconnect()


class MentionNotificationWebsocketTests(TransactionTestCase):
	reset_sequences = True

	def test_mention_notification_uses_at_name(self):
		sender = User.objects.create_user(email='m-sender@example.com', password='password123', name='Sender')
		alice = User.objects.create_user(email='alice@example.com', password='password123', name='Alice')
		bob = User.objects.create_user(email='bob@example.com', password='password123', name='Bob')

		workspace = Workspace.objects.create(name='WS')
		channel = Channel.objects.create(name='General', type='public', is_active=True)
		workspace.channels.add(channel)
		channel.users.add(sender, alice, bob)

		sender_token = str(AccessToken.for_user(sender))
		alice_token = str(AccessToken.for_user(alice))

		async_to_sync(self._assert_mention)(
			sender_token=sender_token,
			alice_token=alice_token,
			channel_id=channel.id,
			alice_id=alice.id,
			bob_id=bob.id,
		)

	async def _assert_mention(self, *, sender_token: str, alice_token: str, channel_id: int, alice_id: int, bob_id: int):
		alice_notify = WebsocketCommunicator(application, f"/ws/notifications/?token={alice_token}")
		connected_a, _ = await alice_notify.connect()
		self.assertTrue(connected_a)
		_ = await alice_notify.receive_json_from()  # notifications.init

		channel_ws = WebsocketCommunicator(application, f"/ws/chat/channels/{channel_id}/?token={sender_token}")
		connected_c, _ = await channel_ws.connect()
		self.assertTrue(connected_c)
		_ = await channel_ws.receive_json_from()  # history

		await channel_ws.send_json_to({'type': 'message.send', 'content': 'Hello @Alice'})
		_ = await channel_ws.receive_json_from()  # message.new

		event = await alice_notify.receive_json_from()
		self.assertEqual(event.get('type'), 'notification.new')
		self.assertEqual(event['notification']['notification_type'], 'chat.mention')
		self.assertEqual(event['notification']['title'], 'New message')

		alice_count = await database_sync_to_async(Notification.objects.filter(user_id=alice_id).count)()
		bob_count = await database_sync_to_async(Notification.objects.filter(user_id=bob_id).count)()
		self.assertEqual(alice_count, 1)
		self.assertEqual(bob_count, 1)

		# Ensure Alice didn't get both mention + generic
		alice_types = await database_sync_to_async(list)(
			Notification.objects.filter(user_id=alice_id).values_list('notification_type', flat=True)
		)
		self.assertEqual(alice_types, ['chat.mention'])

		await channel_ws.disconnect()
		await alice_notify.disconnect()

	def test_mention_notification_supports_spaces_in_name(self):
		sender = User.objects.create_user(email='m-sender2@example.com', password='password123', name='Sender')
		alice = User.objects.create_user(email='alice2@example.com', password='password123', name='Alice Smith')
		bob = User.objects.create_user(email='bob2@example.com', password='password123', name='Bob')

		workspace = Workspace.objects.create(name='WS')
		channel = Channel.objects.create(name='General', type='public', is_active=True)
		workspace.channels.add(channel)
		channel.users.add(sender, alice, bob)

		sender_token = str(AccessToken.for_user(sender))
		alice_token = str(AccessToken.for_user(alice))

		async_to_sync(self._assert_mention_with_content)(
			sender_token=sender_token,
			alice_token=alice_token,
			channel_id=channel.id,
			alice_id=alice.id,
			content='Hello @Alice Smith',
		)

	async def _assert_mention_with_content(self, *, sender_token: str, alice_token: str, channel_id: int, alice_id: int, content: str):
		alice_notify = WebsocketCommunicator(application, f"/ws/notifications/?token={alice_token}")
		connected_a, _ = await alice_notify.connect()
		self.assertTrue(connected_a)
		_ = await alice_notify.receive_json_from()  # notifications.init

		channel_ws = WebsocketCommunicator(application, f"/ws/chat/channels/{channel_id}/?token={sender_token}")
		connected_c, _ = await channel_ws.connect()
		self.assertTrue(connected_c)
		_ = await channel_ws.receive_json_from()  # history

		await channel_ws.send_json_to({'type': 'message.send', 'content': content})
		_ = await channel_ws.receive_json_from()  # message.new

		event = await alice_notify.receive_json_from()
		self.assertEqual(event.get('type'), 'notification.new')
		self.assertEqual(event['notification']['notification_type'], 'chat.mention')
		self.assertEqual(event['notification']['title'], 'New message')

		alice_types = await database_sync_to_async(list)(
			Notification.objects.filter(user_id=alice_id).values_list('notification_type', flat=True)
		)
		self.assertEqual(alice_types, ['chat.mention'])

		await channel_ws.disconnect()
		await alice_notify.disconnect()


class ChatAttachmentWebsocketTests(TransactionTestCase):
	reset_sequences = True

	def test_can_send_attachment_message_over_ws(self):
		sender = User.objects.create_user(email='att-sender@example.com', password='password123', name='Sender')
		workspace = Workspace.objects.create(name='WS')
		channel = Channel.objects.create(name='General', type='public', is_active=True)
		workspace.channels.add(channel)
		channel.users.add(sender)

		token = str(AccessToken.for_user(sender))
		async_to_sync(self._assert_attachment_flow)(
			token=token,
			sender_id=sender.id,
			channel_id=channel.id,
		)

	def _upload_file(self, *, sender_id: int) -> dict:
		sender = User.objects.get(id=sender_id)
		client = APIClient()
		client.force_authenticate(user=sender)
		url = reverse('chat-upload')
		f = SimpleUploadedFile('hello.txt', b'hello world', content_type='text/plain')
		resp = client.post(url, {'file': f, 'kind': 'file'}, format='multipart')
		return {'status_code': int(resp.status_code), 'data': resp.data}

	async def _assert_attachment_flow(self, *, token: str, sender_id: int, channel_id: int):
		upload_res = await database_sync_to_async(self._upload_file)(sender_id=sender_id)
		self.assertEqual(upload_res['status_code'], status.HTTP_201_CREATED)
		attachment_id = int(upload_res['data']['id'])

		ws = WebsocketCommunicator(application, f"/ws/chat/channels/{channel_id}/?token={token}")
		connected, _ = await ws.connect()
		self.assertTrue(connected)
		history = await ws.receive_json_from()
		self.assertEqual(history.get('type'), 'history')

		await ws.send_json_to({'type': 'message.send', 'content': '', 'attachment_ids': [attachment_id]})
		event = await ws.receive_json_from()
		self.assertEqual(event.get('type'), 'message.new')
		self.assertIn('attachments', event['message'])
		self.assertEqual(len(event['message']['attachments']), 1)
		self.assertEqual(int(event['message']['attachments'][0]['id']), attachment_id)
		self.assertTrue(bool(event['message']['attachments'][0].get('url')))

		linked = await database_sync_to_async(ChatAttachment.objects.filter(id=attachment_id, message__isnull=False).count)()
		self.assertEqual(int(linked), 1)

		await ws.disconnect()


class DirectMessageNotificationWebsocketTests(TransactionTestCase):
	reset_sequences = True

	def test_dm_notification_created_and_delivered_when_recipient_not_in_dm_room(self):
		sender = User.objects.create_user(email='dm-sender@example.com', password='password123')
		recipient = User.objects.create_user(email='dm-recipient@example.com', password='password123')
		sender_token = str(AccessToken.for_user(sender))
		recipient_token = str(AccessToken.for_user(recipient))

		async_to_sync(self._assert_dm_notification_delivery)(
			sender_token=sender_token,
			recipient_token=recipient_token,
			recipient_id=recipient.id,
		)

	async def _assert_dm_notification_delivery(self, *, sender_token: str, recipient_token: str, recipient_id: int):
		recipient_notifs = WebsocketCommunicator(application, f"/ws/notifications/?token={recipient_token}")
		connected_n, _ = await recipient_notifs.connect()
		self.assertTrue(connected_n)
		init = await recipient_notifs.receive_json_from()
		self.assertEqual(init.get('type'), 'notifications.init')

		sender_dm = WebsocketCommunicator(application, f"/ws/chat/dm/{recipient_id}/?token={sender_token}")
		connected_s, _ = await sender_dm.connect()
		self.assertTrue(connected_s)
		_ = await sender_dm.receive_json_from()  # history

		await sender_dm.send_json_to({'type': 'message.send', 'content': 'Hi there'})
		msg_event = await sender_dm.receive_json_from()
		self.assertEqual(msg_event.get('type'), 'message.new')

		n_event = await recipient_notifs.receive_json_from()
		self.assertEqual(n_event.get('type'), 'notification.new')
		self.assertEqual(n_event['notification']['notification_type'], 'chat.direct_message')

		await sender_dm.disconnect()
		await recipient_notifs.disconnect()

	def test_dm_notification_suppressed_when_recipient_connected_to_dm_room(self):
		sender = User.objects.create_user(email='dm-sender2@example.com', password='password123')
		recipient = User.objects.create_user(email='dm-recipient2@example.com', password='password123')
		sender_token = str(AccessToken.for_user(sender))
		recipient_token = str(AccessToken.for_user(recipient))

		async_to_sync(self._assert_dm_suppression)(
			sender_token=sender_token,
			recipient_token=recipient_token,
			sender_id=sender.id,
			recipient_id=recipient.id,
		)

	async def _assert_dm_suppression(self, *, sender_token: str, recipient_token: str, sender_id: int, recipient_id: int):
		# Both users connect to the same DM room (same thread)
		recipient_dm = WebsocketCommunicator(application, f"/ws/chat/dm/{sender_id}/?token={recipient_token}")
		sender_dm = WebsocketCommunicator(application, f"/ws/chat/dm/{recipient_id}/?token={sender_token}")

		connected_r, _ = await recipient_dm.connect()
		self.assertTrue(connected_r)
		_ = await recipient_dm.receive_json_from()  # history

		connected_s, _ = await sender_dm.connect()
		self.assertTrue(connected_s)
		_ = await sender_dm.receive_json_from()  # history

		await sender_dm.send_json_to({'type': 'message.send', 'content': 'Hello'})
		_ = await sender_dm.receive_json_from()  # message.new
		_ = await recipient_dm.receive_json_from()  # message.new

		count_connected = await database_sync_to_async(Notification.objects.filter(user_id=recipient_id).count)()
		self.assertEqual(count_connected, 0)

		await recipient_dm.disconnect()

		await sender_dm.send_json_to({'type': 'message.send', 'content': 'Hello again'})
		_ = await sender_dm.receive_json_from()  # message.new
		count_disconnected = await database_sync_to_async(Notification.objects.filter(user_id=recipient_id).count)()
		self.assertEqual(count_disconnected, 1)

		await sender_dm.disconnect()


class MentionNotificationTests(TransactionTestCase):
	reset_sequences = True

	def test_mention_creates_mention_notification(self):
		sender = User.objects.create_user(email='m-sender@example.com', password='password123')
		mentioned = User.objects.create_user(email='mentioned@example.com', password='password123', name='Mentioned')
		other = User.objects.create_user(email='other@example.com', password='password123')

		workspace = Workspace.objects.create(name='WS')
		channel = Channel.objects.create(name='General', type='public', is_active=True)
		workspace.channels.add(channel)
		channel.users.add(sender, mentioned, other)

		sender_token = str(AccessToken.for_user(sender))
		async_to_sync(self._assert_mention_notification)(
			sender_token=sender_token,
			channel_id=channel.id,
			mentioned_id=mentioned.id,
			other_id=other.id,
		)

	async def _assert_mention_notification(self, *, sender_token: str, channel_id: int, mentioned_id: int, other_id: int):
		sender_ws = WebsocketCommunicator(application, f"/ws/chat/channels/{channel_id}/?token={sender_token}")
		connected_s, _ = await sender_ws.connect()
		self.assertTrue(connected_s)
		_ = await sender_ws.receive_json_from()  # history

		await sender_ws.send_json_to({'type': 'message.send', 'content': 'Hi @Mentioned'})
		_ = await sender_ws.receive_json_from()  # message.new

		m_types = await database_sync_to_async(list)(
			Notification.objects.filter(user_id=mentioned_id).values_list('notification_type', flat=True)
		)
		self.assertIn('chat.mention', m_types)
		self.assertNotIn('chat.channel_message', m_types)

		o_types = await database_sync_to_async(list)(
			Notification.objects.filter(user_id=other_id).values_list('notification_type', flat=True)
		)
		self.assertIn('chat.channel_message', o_types)

		await sender_ws.disconnect()
