from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User, Role
from Communication.models import Workspace, Channel, ChatMessage

from Admin.models import Automation
from Notification.models import SystemSettings, NotificationPreference

from unittest.mock import patch


class AdminActivationEndpointsTests(APITestCase):
	def setUp(self):
		self.admin_role = Role.objects.create(name='Admin', slug='admin')
		self.admin_user = User.objects.create_user(
			email='admin-activate@example.com',
			password='password123',
			role=self.admin_role,
		)
		self.normal_user = User.objects.create_user(
			email='normal@example.com',
			password='password123',
		)

		self.channel = Channel.objects.create(name='Chan', type='public', is_active=True)
		self.workspace = Workspace.objects.create(name='WS', is_active=True)

	def test_non_admin_cannot_deactivate_channel(self):
		self.client.force_authenticate(user=self.normal_user)
		url = reverse('admin-channel-status', kwargs={'pk': self.channel.id})
		response = self.client.post(url, {'is_active': False}, format='json')
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_admin_can_deactivate_and_activate_channel(self):
		self.client.force_authenticate(user=self.admin_user)

		url = reverse('admin-channel-status', kwargs={'pk': self.channel.id})
		response = self.client.post(url, {'is_active': False}, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.channel.refresh_from_db()
		self.assertFalse(self.channel.is_active)

		url = reverse('admin-channel-status', kwargs={'pk': self.channel.id})
		response = self.client.post(url, {'is_active': True}, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.channel.refresh_from_db()
		self.assertTrue(self.channel.is_active)

	def test_admin_can_deactivate_workspace(self):
		self.client.force_authenticate(user=self.admin_user)
		url = reverse('admin-workspace-status', kwargs={'pk': self.workspace.id})
		response = self.client.post(url, {'is_active': False}, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.workspace.refresh_from_db()
		self.assertFalse(self.workspace.is_active)

	def test_admin_can_deactivate_user(self):
		self.client.force_authenticate(user=self.admin_user)
		url = reverse('admin-user-status', kwargs={'pk': self.normal_user.id})
		response = self.client.post(url, {'is_active': False}, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.normal_user.refresh_from_db()
		self.assertFalse(self.normal_user.is_active)


class AdminAutomationsTests(APITestCase):
	def setUp(self):
		self.admin_role = Role.objects.create(name='Admin', slug='admin')
		self.admin_user = User.objects.create_user(
			email='admin-automations@example.com',
			password='password123',
			role=self.admin_role,
		)
		self.user = User.objects.create_user(email='user@example.com', password='password123')
		self.client.force_authenticate(user=self.admin_user)

	def test_create_list_and_update_automation(self):
		url = reverse('admin-automation-list')
		payload = {
			'name': 'Welcome Message',
			'workspace_id': None,
			'trigger_type': Automation.TRIGGER_USER_JOINS,
			'action_type': Automation.ACTION_SEND_MESSAGE,
			'message_content': 'Welcome!',
			'is_enabled': True,
		}
		create_resp = self.client.post(url, payload, format='json')
		self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)

		list_resp = self.client.get(url)
		self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
		self.assertIn('active_automations', list_resp.data)
		self.assertIn('total_executions', list_resp.data)
		self.assertIn('success_rate', list_resp.data)
		self.assertIn('time_saved_hours', list_resp.data)
		self.assertIn('automations', list_resp.data)
		self.assertEqual(len(list_resp.data['automations']), 1)

		automation_id = create_resp.data['id']
		detail_url = reverse('admin-automation-detail', kwargs={'pk': automation_id})
		patch_resp = self.client.patch(detail_url, {'is_enabled': False}, format='json')
		self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
		self.assertFalse(patch_resp.data['is_enabled'])

	def test_user_joins_triggers_send_message_automation(self):
		Automation.objects.create(
			name='Welcome',
			trigger_type=Automation.TRIGGER_USER_JOINS,
			action_type=Automation.ACTION_SEND_MESSAGE,
			message_content='Hello new user',
			is_enabled=True,
			created_by=self.admin_user,
		)

		ws = Workspace.objects.create(name='WS')

		# Join workspace as normal user
		self.client.force_authenticate(user=self.user)
		join_url = reverse('workspace-join', kwargs={'slug': ws.slug})
		resp = self.client.post(join_url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)

		self.assertTrue(
			ChatMessage.objects.filter(
				sender=self.admin_user,
				dm_thread__isnull=False,
				content='Hello new user',
			).exists()
		)

	def test_new_message_automation_creates_channel_reply(self):
		Automation.objects.create(
			name='Auto Reply',
			trigger_type=Automation.TRIGGER_NEW_MESSAGE,
			action_type=Automation.ACTION_SEND_MESSAGE,
			message_content='Auto reply',
			is_enabled=True,
			created_by=self.admin_user,
		)

		channel = Channel.objects.create(name='C', type='public')
		channel.users.add(self.user)
		channel.users.add(self.admin_user)

		original = ChatMessage.objects.create(sender=self.user, channel=channel, content='Hi')

		from Admin.automation_engine import run_new_channel_message

		created = run_new_channel_message(message=original)
		self.assertEqual(len(created), 1)
		self.assertEqual(created[0].sender_id, self.admin_user.id)
		self.assertEqual(created[0].channel_id, channel.id)
		self.assertEqual(created[0].content, 'Auto reply')

	def test_new_message_automation_respects_system_auto_reply_toggle(self):
		SystemSettings.objects.update_or_create(id=1, defaults={'auto_reply_enabled': False})
		Automation.objects.create(
			name='Auto Reply',
			trigger_type=Automation.TRIGGER_NEW_MESSAGE,
			action_type=Automation.ACTION_SEND_MESSAGE,
			message_content='Auto reply',
			is_enabled=True,
			created_by=self.admin_user,
		)

		channel = Channel.objects.create(name='C2', type='public')
		channel.users.add(self.user)
		channel.users.add(self.admin_user)
		original = ChatMessage.objects.create(sender=self.user, channel=channel, content='Hi')

		from Admin.automation_engine import run_new_channel_message

		created = run_new_channel_message(message=original)
		self.assertEqual(created, [])
		self.assertFalse(ChatMessage.objects.filter(sender=self.admin_user, channel=channel, content='Auto reply').exists())

	@patch('Admin.automation_engine.send_mail')
	def test_send_email_automation_respects_user_and_system_email_preferences(self, send_mail_mock):
		# System email disabled => should not send
		SystemSettings.objects.update_or_create(id=1, defaults={'email_notifications_enabled': False})
		NotificationPreference.objects.update_or_create(
			user=self.user,
			defaults={'email_mentions': True, 'email_direct_messages': True},
		)
		Automation.objects.create(
			name='Email on new message',
			trigger_type=Automation.TRIGGER_NEW_MESSAGE,
			action_type=Automation.ACTION_SEND_EMAIL,
			message_content='Email body',
			is_enabled=True,
			created_by=self.admin_user,
		)
		channel = Channel.objects.create(name='C3', type='public')
		channel.users.add(self.user)
		channel.users.add(self.admin_user)
		original = ChatMessage.objects.create(sender=self.user, channel=channel, content='Hi')

		from Admin.automation_engine import run_new_channel_message
		run_new_channel_message(message=original)
		send_mail_mock.assert_not_called()

		# Enable system email, but user email_mentions disabled => still should not send
		SystemSettings.objects.update_or_create(id=1, defaults={'email_notifications_enabled': True})
		NotificationPreference.objects.update_or_create(
			user=self.user,
			defaults={'email_mentions': False, 'email_direct_messages': True},
		)
		run_new_channel_message(message=original)
		send_mail_mock.assert_not_called()

		# Enable user email_mentions => should send now
		NotificationPreference.objects.update_or_create(
			user=self.user,
			defaults={'email_mentions': True, 'email_direct_messages': True},
		)
		run_new_channel_message(message=original)
		self.assertTrue(send_mail_mock.called)
