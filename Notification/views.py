from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from authentication.permissions import IsAdmin

from .models import NotificationPreference, SystemSettings, Notification
from .serializers import NotificationPreferenceSerializer, SystemSettingsSerializer, NotificationSerializer
from .services import mark_all_as_read


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
