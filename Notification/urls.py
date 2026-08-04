from django.urls import path

from .views import (
	MyNotificationPreferenceView,
	MyNotificationsView,
	MarkAllNotificationsReadView,
	DeviceTokenRegisterView,
	DeviceTokenUnregisterView,
	TestPushNotificationView,
)


urlpatterns = [
	path('', MyNotificationsView.as_view(), name='my-notifications'),
	path('preferences/', MyNotificationPreferenceView.as_view(), name='notification-preferences'),
	path('mark-all-read/', MarkAllNotificationsReadView.as_view(), name='notifications-mark-all-read'),
	path('devices/register/', DeviceTokenRegisterView.as_view(), name='device-token-register'),
	path('devices/unregister/', DeviceTokenUnregisterView.as_view(), name='device-token-unregister'),
	path('devices/test/', TestPushNotificationView.as_view(), name='device-push-test'),
]