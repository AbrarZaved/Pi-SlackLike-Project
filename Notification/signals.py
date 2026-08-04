from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from authentication.models import User

from .models import NotificationPreference
from .services import create_notification_for_user, create_notifications_for_role


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance: User, created: bool, **kwargs):
	if kwargs.get('raw', False):
		return
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

@receiver(pre_save, sender=User)
def capture_previous_user_flags(sender, instance: User, **kwargs):
	"""Remember is_active / role so post_save can detect what changed."""
	if kwargs.get('raw', False) or not instance.pk:
		instance._prev_is_active = None
		instance._prev_role_id = None
		return

	previous = User.objects.filter(pk=instance.pk).only('is_active', 'role').first()
	instance._prev_is_active = getattr(previous, 'is_active', None)
	instance._prev_role_id = getattr(previous, 'role_id', None)


@receiver(post_save, sender=User)
def notify_user_account_changes(sender, instance: User, created: bool, **kwargs):
	"""Notify a user when an admin activates/deactivates them or changes their role."""
	if kwargs.get('raw', False) or created:
		return

	prev_is_active = getattr(instance, '_prev_is_active', None)
	prev_role_id = getattr(instance, '_prev_role_id', None)

	try:
		if prev_is_active is not None and prev_is_active != instance.is_active:
			create_notification_for_user(
				user=instance,
				notification_type='account.activated' if instance.is_active else 'account.deactivated',
				title='Account reactivated' if instance.is_active else 'Account deactivated',
				body=(
					'Your account is active again. Welcome back!'
					if instance.is_active
					else 'Your account has been deactivated by an administrator.'
				),
				data={'user_id': instance.id, 'is_active': instance.is_active},
			)

		if prev_role_id is not None and prev_role_id != instance.role_id:
			role_name = getattr(instance.role, 'name', None) or 'None'
			create_notification_for_user(
				user=instance,
				notification_type='account.role_changed',
				title='Your role was updated',
				body=f'Your new role is: {role_name}',
				data={
					'user_id': instance.id,
					'role_id': instance.role_id,
					'role_name': role_name,
				},
			)
	except Exception:
		# Never break user updates due to the notification system
		pass