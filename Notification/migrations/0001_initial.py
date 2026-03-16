# Generated manually for Notification app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
	initial = True

	dependencies = [
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
	]

	operations = [
		migrations.CreateModel(
			name='SystemSettings',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('email_notifications_enabled', models.BooleanField(default=True)),
				('push_notifications_enabled', models.BooleanField(default=True)),
				('auto_reply_enabled', models.BooleanField(default=True)),
				('file_sharing_enabled', models.BooleanField(default=True)),
				('video_calls_enabled', models.BooleanField(default=True)),
				('screen_sharing_enabled', models.BooleanField(default=True)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('updated_at', models.DateTimeField(auto_now=True)),
			],
			options={
				'verbose_name': 'System Settings',
				'verbose_name_plural': 'System Settings',
			},
		),
		migrations.CreateModel(
			name='NotificationPreference',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('email_direct_messages', models.BooleanField(default=True)),
				('email_mentions', models.BooleanField(default=True)),
				('push_mobile_notifications', models.BooleanField(default=True)),
				('push_sound_alerts', models.BooleanField(default=True)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('updated_at', models.DateTimeField(auto_now=True)),
				('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
			],
			options={
				'verbose_name': 'Notification Preference',
				'verbose_name_plural': 'Notification Preferences',
			},
		),
	]
