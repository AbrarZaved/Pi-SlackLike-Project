# Generated manually for DeviceToken model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
	dependencies = [
		('Notification', '0002_notification'),
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
	]

	operations = [
		migrations.CreateModel(
			name='DeviceToken',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('token', models.CharField(max_length=512, unique=True)),
				('platform', models.CharField(choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')], default='android', max_length=16)),
				('device_id', models.CharField(blank=True, max_length=255)),
				('is_active', models.BooleanField(default=True)),
				('last_used_at', models.DateTimeField(auto_now=True)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_tokens', to=settings.AUTH_USER_MODEL)),
			],
			options={
				'verbose_name': 'Device Token',
				'verbose_name_plural': 'Device Tokens',
				'ordering': ['-created_at'],
			},
		),
		migrations.AddIndex(
			model_name='devicetoken',
			index=models.Index(fields=['user', 'is_active'], name='notif_devtok_user_act_idx'),
		),
	]