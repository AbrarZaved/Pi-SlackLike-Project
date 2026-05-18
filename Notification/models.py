from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='notification_preferences',
	)

	# Email notifications
	email_direct_messages = models.BooleanField(default=True)
	email_mentions = models.BooleanField(default=True)

	# Push notifications
	push_mobile_notifications = models.BooleanField(default=True)
	push_sound_alerts = models.BooleanField(default=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'Notification Preference'
		verbose_name_plural = 'Notification Preferences'

	def __str__(self):
		return f"NotificationPreference(user_id={self.user_id})"


class SystemSettings(models.Model):
	"""Singleton-ish system settings row controlled by admins."""

	# Notification Rules
	email_notifications_enabled = models.BooleanField(default=True)
	push_notifications_enabled = models.BooleanField(default=True)

	# Feature Toggles
	auto_reply_enabled = models.BooleanField(default=True)
	file_sharing_enabled = models.BooleanField(default=True)
	video_calls_enabled = models.BooleanField(default=True)
	screen_sharing_enabled = models.BooleanField(default=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'System Settings'
		verbose_name_plural = 'System Settings'

	def __str__(self):
		return f"SystemSettings(id={self.id})"


class Notification(models.Model):
	"""A stored in-app notification for a specific user.

	Notifications are delivered in real-time over websocket when allowed by
	system settings and the user's push preferences.
	"""

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='notifications',
	)
	target_role_slug = models.SlugField(blank=True, null=True)

	notification_type = models.CharField(max_length=64)
	title = models.CharField(max_length=255)
	body = models.TextField(blank=True, null=True)
	data = models.JSONField(default=dict, blank=True)

	is_read = models.BooleanField(default=False)
	read_at = models.DateTimeField(blank=True, null=True)

	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = 'Notification'
		verbose_name_plural = 'Notifications'
		ordering = ['-created_at']

	def __str__(self):
		return f"Notification(id={self.id}, user_id={self.user_id}, type={self.notification_type})"
