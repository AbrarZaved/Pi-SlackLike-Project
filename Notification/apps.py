from django.apps import AppConfig


class NotificationConfig(AppConfig):
	default_auto_field = 'django.db.models.BigAutoField'
	name = 'Notification'

	def ready(self):
		from . import signals  # noqa: F401
