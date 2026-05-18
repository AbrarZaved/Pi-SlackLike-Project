from django.urls import path

from .views import MyNotificationPreferenceView, MyNotificationsView, MarkAllNotificationsReadView


urlpatterns = [
	path('', MyNotificationsView.as_view(), name='my-notifications'),
	path('preferences/', MyNotificationPreferenceView.as_view(), name='notification-preferences'),
	path('mark-all-read/', MarkAllNotificationsReadView.as_view(), name='notifications-mark-all-read'),
]
