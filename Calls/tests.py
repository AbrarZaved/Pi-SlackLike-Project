from django.urls import reverse
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User, Role, Permission
from Communication.models import Workspace, Channel, DirectMessageThread


@override_settings(
	LIVEKIT_API_KEY='test_key',
	LIVEKIT_API_SECRET='test_secret',
	LIVEKIT_URL='wss://example.livekit.cloud',
)
class CallFlowTests(APITestCase):
	def setUp(self):
		calling = Permission.objects.create(
			codename='calling',
			name='Calling',
			category='communication',
			description='test',
		)
		screen_share = Permission.objects.create(
			codename='screen_share',
			name='Screen Share',
			category='communication',
			description='test',
		)
		role = Role.objects.create(name='Team Member', slug='team_member')
		role.permissions.add(calling, screen_share)

		role_no_screen = Role.objects.create(name='Business User', slug='business_user')
		role_no_screen.permissions.add(calling)

		self.u1 = User.objects.create_user(email='u1@example.com', password='password123', role=role)
		self.u2 = User.objects.create_user(email='u2@example.com', password='password123', role=role_no_screen)

		self.workspace = Workspace.objects.create(name='WS', user=self.u1)
		self.workspace.users.add(self.u1, self.u2)

		self.channel = Channel.objects.create(name='CH', type='public', user=self.u1)
		self.channel.users.add(self.u1, self.u2)

	def test_create_workspace_call_and_token(self):
		self.client.force_authenticate(user=self.u1)
		create_url = reverse('call-create')

		resp = self.client.post(create_url, {
			'context_type': 'workspace',
			'workspace_id': self.workspace.id,
			'participant_ids': [self.u2.id],
			'is_video': True,
		}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
		call_id = resp.data['id']

		token_url = reverse('call-token', kwargs={'call_id': call_id})
		token_resp = self.client.post(token_url)
		self.assertEqual(token_resp.status_code, status.HTTP_200_OK)
		self.assertIn('token', token_resp.data)
		self.assertTrue(token_resp.data['can_screen_share'])

		# invited user can also get token but without screen share permission
		self.client.force_authenticate(user=self.u2)
		token_resp2 = self.client.post(token_url)
		self.assertEqual(token_resp2.status_code, status.HTTP_200_OK)
		self.assertFalse(token_resp2.data['can_screen_share'])

		# logs should include the call for participants
		logs_url = reverse('call-logs')
		logs_resp = self.client.get(logs_url)
		self.assertEqual(logs_resp.status_code, status.HTTP_200_OK)
		self.assertTrue(any(item['id'] == call_id for item in logs_resp.data))

		# leave should set left_at and reduce active count
		leave_url = reverse('call-leave', kwargs={'call_id': call_id})
		leave_resp = self.client.post(leave_url)
		self.assertEqual(leave_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(leave_resp.data['left_participants'], 1)
		self.assertEqual(leave_resp.data['active_participants'], 1)

		# summary should be accessible and include participant counts
		summary_url = reverse('call-summary', kwargs={'call_id': call_id})
		summary_resp = self.client.get(summary_url)
		self.assertEqual(summary_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(summary_resp.data['total_participants'], 2)
		self.assertGreaterEqual(summary_resp.data['joined_participants'], 1)

	def test_create_channel_call(self):
		self.client.force_authenticate(user=self.u1)
		create_url = reverse('call-create')

		resp = self.client.post(create_url, {
			'context_type': 'channel',
			'channel_id': self.channel.id,
			'participant_ids': [self.u2.id],
		}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

	def test_create_dm_call_requires_two_participants(self):
		thread = DirectMessageThread.get_or_create_for_users(self.u1, self.u2)
		self.client.force_authenticate(user=self.u1)
		create_url = reverse('call-create')

		bad = self.client.post(create_url, {
			'context_type': 'dm',
			'dm_thread_id': thread.id,
			'participant_ids': [self.u2.id, self.u1.id, 9999],
		}, format='json')
		self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

		ok = self.client.post(create_url, {
			'context_type': 'dm',
			'dm_thread_id': thread.id,
			'participant_ids': [self.u2.id],
		}, format='json')
		self.assertEqual(ok.status_code, status.HTTP_201_CREATED)


# Create your tests here.
