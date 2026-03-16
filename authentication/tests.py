from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User, Role
from Communication.models import Workspace


class UserListSummaryTests(APITestCase):
	def setUp(self):
		admin_role = Role.objects.create(name='Admin', slug='admin')
		self.admin_user = User.objects.create_user(
			email='admin@example.com',
			password='password123',
			role=admin_role,
		)
		self.client.force_authenticate(user=self.admin_user)

	def test_user_list_includes_total_active_inactive_counts(self):
		# 1 active (admin_user) already exists
		User.objects.create_user(email='u1@example.com', password='password123', is_active=True)
		User.objects.create_user(email='u2@example.com', password='password123', is_active=False)

		Workspace.objects.create(name='Admin WS', user=self.admin_user)
		self.admin_user.last_login = timezone.now() - timedelta(minutes=2)
		self.admin_user.save(update_fields=['last_login'])

		url = reverse('user-list')
		response = self.client.get(url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('total_users', response.data)
		self.assertIn('total_active_users', response.data)
		self.assertIn('total_inactive_users', response.data)
		self.assertIn('count', response.data)
		self.assertIn('results', response.data)

		self.assertEqual(response.data['total_users'], 3)
		self.assertEqual(response.data['total_active_users'], 2)
		self.assertEqual(response.data['total_inactive_users'], 1)
		self.assertEqual(response.data['count'], 3)

		admin_row = next(row for row in response.data['results'] if row['id'] == self.admin_user.id)
		self.assertIn('created_workspaces', admin_row)
		self.assertIn('Admin WS', admin_row['created_workspaces'])
		self.assertIn('last_active', admin_row)
		self.assertIsNotNone(admin_row['last_active'])

	def test_user_list_counts_respect_search_filter(self):
		User.objects.create_user(email='alpha@example.com', password='password123', is_active=True, name='Alpha')
		User.objects.create_user(email='beta@example.com', password='password123', is_active=False, name='Beta')

		url = reverse('user-list')
		response = self.client.get(url, {'search': 'alpha'})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['total_users'], 1)
		self.assertEqual(response.data['total_active_users'], 1)
		self.assertEqual(response.data['total_inactive_users'], 0)
		self.assertEqual(response.data['count'], 1)
