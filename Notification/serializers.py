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


class TestPushNotificationSerializer(serializers.Serializer):
	"""Input for the test push endpoint."""

	title = serializers.CharField(max_length=255, required=False, default='🔔 Test notification')
	body = serializers.CharField(
		required=False,
		allow_blank=True,
		default='This is a test push notification from the Pi backend.',
	)
	data = serializers.DictField(required=False, default=dict)

	# Admin-only targeting options. Omit both to push to your own devices.
	user_id = serializers.IntegerField(required=False, allow_null=True)
	token = serializers.CharField(required=False, allow_blank=True)

	# When True, also stores an in-app Notification row and broadcasts it
	# over the websocket (i.e. full end-to-end test).
	save_notification = serializers.BooleanField(required=False, default=False)

	def validate(self, attrs):
		if attrs.get('user_id') and (attrs.get('token') or '').strip():
			raise serializers.ValidationError('Provide either user_id or token, not both.')
		return attrs