# Generated manually for Notification model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
	dependencies = [
		('Notification', '0001_initial'),
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
	]

	operations = [
		migrations.CreateModel(
			name='Notification',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('target_role_slug', models.SlugField(blank=True, null=True)),
				('notification_type', models.CharField(max_length=64)),
				('title', models.CharField(max_length=255)),
				('body', models.TextField(blank=True, null=True)),
				('data', models.JSONField(blank=True, default=dict)),
				('is_read', models.BooleanField(default=False)),
				('read_at', models.DateTimeField(blank=True, null=True)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
			],
			options={
				'verbose_name': 'Notification',
				'verbose_name_plural': 'Notifications',
				'ordering': ['-created_at'],
			},
		),
	]
