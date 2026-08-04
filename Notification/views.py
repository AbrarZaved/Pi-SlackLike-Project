from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from authentication.permissions import IsAdmin

from .models import NotificationPreference, SystemSettings, Notification, DeviceToken
from .serializers import (
	NotificationPreferenceSerializer,
	SystemSettingsSerializer,
	NotificationSerializer,
	DeviceTokenSerializer,
	TestPushNotificationSerializer,
)
from .services import mark_all_as_read, create_notification_for_user
from .push import send_push_to_tokens


class MyNotificationPreferenceView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
		return Response(NotificationPreferenceSerializer(prefs).data)

	def patch(self, request):
		prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
		serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return Response(serializer.data)


class AdminSystemSettingsView(APIView):
	permission_classes = [IsAuthenticated, IsAdmin]

	def _get_settings(self) -> SystemSettings:
		obj, _ = SystemSettings.objects.get_or_create(id=1)
		return obj

	def get(self, request):
		obj = self._get_settings()
		return Response(SystemSettingsSerializer(obj).data)

	def patch(self, request):
		obj = self._get_settings()
		serializer = SystemSettingsSerializer(obj, data=request.data, partial=True)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return Response(serializer.data)


class MyNotificationsView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		qs = Notification.objects.filter(user=request.user).order_by('-created_at')
		unread_count = qs.filter(is_read=False).count()
		items = NotificationSerializer(qs[:50], many=True).data
		return Response({'unread_count': unread_count, 'notifications': items})


class MarkAllNotificationsReadView(APIView):
	permission_classes = [IsAuthenticated]

	def post(self, request):
		updated = mark_all_as_read(user=request.user)
		return Response({'marked_read': updated}, status=status.HTTP_200_OK)


class DeviceTokenRegisterView(APIView):
	"""Register (or refresh) the caller's FCM device token."""

	permission_classes = [IsAuthenticated]
	serializer_class = DeviceTokenSerializer

	def post(self, request):
		serializer = DeviceTokenSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		token = serializer.validated_data['token']
		defaults = {
			'user': request.user,
			'platform': serializer.validated_data.get('platform', DeviceToken.PLATFORM_ANDROID),
			'device_id': serializer.validated_data.get('device_id', ''),
			'is_active': True,
		}

		# A token belongs to exactly one device, so re-assign it on login.
		obj, created = DeviceToken.objects.update_or_create(token=token, defaults=defaults)

		return Response(
			DeviceTokenSerializer(obj).data,
			status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
		)


class DeviceTokenUnregisterView(APIView):
	"""Deactivate a device token (call this on logout)."""

	permission_classes = [IsAuthenticated]

	def post(self, request):
		token = (request.data.get('token') or '').strip()
		if not token:
			return Response({'error': 'token is required'}, status=status.HTTP_400_BAD_REQUEST)

		updated = DeviceToken.objects.filter(user=request.user, token=token).update(is_active=False)
		return Response({'unregistered': bool(updated)}, status=status.HTTP_200_OK)


class TestPushNotificationView(APIView):
	"""Send a test push notification to registered devices.

	POST /api/v1/notifications/devices/test/

	Targeting:
	- No target  -> all active devices of the caller.
	- user_id    -> all active devices of that user (admin only).
	- token      -> one raw FCM token, even if not stored (admin only).
	"""

	permission_classes = [IsAuthenticated]
	serializer_class = TestPushNotificationSerializer

	def post(self, request):
		serializer = TestPushNotificationSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		payload = serializer.validated_data

		title = payload.get('title') or '🔔 Test notification'
		body = payload.get('body') or ''
		extra = dict(payload.get('data') or {})
		extra.setdefault('notification_type', 'test')

		raw_token = (payload.get('token') or '').strip()
		target_user_id = payload.get('user_id')

		is_admin = bool(
			getattr(request.user, 'role', None)
			and request.user.role.slug == 'admin'
		)
		if (raw_token or target_user_id) and not is_admin:
			return Response(
				{'error': 'Only admins can send test notifications to other devices.'},
				status=status.HTTP_403_FORBIDDEN,
			)

		# --- Raw token mode: bypass the DB entirely -------------------------
		if raw_token:
			report = send_push_to_tokens(
				tokens=[raw_token],
				title=title,
				body=body,
				data=extra,
				deactivate_stale=False,
			)
			return Response(
				{'target': 'raw_token', 'devices_targeted': 1, **report},
				status=status.HTTP_200_OK,
			)

		# --- User mode ------------------------------------------------------
		target_user = request.user
		if target_user_id:
			target_user = get_user_model().objects.filter(id=target_user_id).first()
			if target_user is None:
				return Response(
					{'error': f'User {target_user_id} not found.'},
					status=status.HTTP_404_NOT_FOUND,
				)

		devices = list(
			DeviceToken.objects.filter(user=target_user, is_active=True)
			.values('token', 'platform', 'device_id')
		)
		if not devices:
			return Response(
				{
					'error': 'No active device tokens registered for this user.',
					'hint': 'Register one first via POST /api/v1/notifications/devices/register/',
					'user_id': target_user.id,
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		# Optional full end-to-end path: stores the row, broadcasts on the
		# websocket and pushes through the normal Celery pipeline.
		if payload.get('save_notification'):
			notification = create_notification_for_user(
				user=target_user,
				notification_type='test',
				title=title,
				body=body,
				data=extra,
			)
			if notification is None:
				return Response(
					{
						'error': 'Push notifications are disabled globally or for this user.',
						'user_id': target_user.id,
					},
					status=status.HTTP_409_CONFLICT,
				)
			return Response(
				{
					'target': 'user',
					'user_id': target_user.id,
					'mode': 'stored_and_queued',
					'notification_id': notification.id,
					'devices_targeted': len(devices),
					'platforms': sorted({d['platform'] for d in devices}),
					'detail': 'Notification stored, broadcast over websocket and queued for FCM.',
				},
				status=status.HTTP_202_ACCEPTED,
			)

		# Default: send straight to FCM now and return the delivery report.
		report = send_push_to_tokens(
			tokens=[d['token'] for d in devices],
			title=title,
			body=body,
			data=extra,
		)
		return Response(
			{
				'target': 'user',
				'user_id': target_user.id,
				'mode': 'direct',
				'devices_targeted': len(devices),
				'platforms': sorted({d['platform'] for d in devices}),
				**report,
			},
			status=status.HTTP_200_OK,
		)