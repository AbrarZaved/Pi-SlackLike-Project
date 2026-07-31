from rest_framework import serializers

from .models import NotificationPreference, SystemSettings, Notification, DeviceToken


class NotificationPreferenceSerializer(serializers.ModelSerializer):
	class Meta:
		model = NotificationPreference
		fields = [
			'email_direct_messages',
			'email_mentions',
			'push_mobile_notifications',
			'push_sound_alerts',
		]


class SystemSettingsSerializer(serializers.ModelSerializer):
	class Meta:
		model = SystemSettings
		fields = [
			'email_notifications_enabled',
			'push_notifications_enabled',
			'auto_reply_enabled',
			'file_sharing_enabled',
			'video_calls_enabled',
			'screen_sharing_enabled',
		]


class NotificationSerializer(serializers.ModelSerializer):
	class Meta:
		model = Notification
		fields = [
			'id',
			'notification_type',
			'title',
			'body',
			'data',
			'is_read',
			'read_at',
			'created_at',
		]


class DeviceTokenSerializer(serializers.ModelSerializer):
	class Meta:
		model = DeviceToken
		fields = ['id', 'token', 'platform', 'device_id', 'is_active', 'created_at']
		read_only_fields = ['id', 'is_active', 'created_at']

	def validate_token(self, value):
		value = (value or '').strip()
		if not value:
			raise serializers.ValidationError('FCM token is required.')
		return value