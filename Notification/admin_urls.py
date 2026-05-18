from django.urls import path

from .views import AdminSystemSettingsView


urlpatterns = [
	path('', AdminSystemSettingsView.as_view(), name='admin-system-settings'),
]
