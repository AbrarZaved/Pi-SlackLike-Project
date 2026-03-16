from django.db.models.signals import post_save
from django.dispatch import receiver

from authentication.models import User

from .models import NotificationPreference
from .services import create_notifications_for_role


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance: User, created: bool, **kwargs):
	if not created:
		return
	NotificationPreference.objects.get_or_create(user=instance)

	# Notify admins about new user creation
	try:
		create_notifications_for_role(
			role_slug='admin',
			notification_type='user.created',
			title='New user joined',
			body=instance.email,
			data={'user_id': instance.id, 'email': instance.email},
		)
	except Exception:
		# Never break user creation due to notification system
		pass
