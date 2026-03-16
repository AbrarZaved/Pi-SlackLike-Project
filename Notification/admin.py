from django.contrib import admin

from .models import NotificationPreference, SystemSettings, Notification


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'email_direct_messages', 'email_mentions', 'push_mobile_notifications', 'push_sound_alerts')
	search_fields = ('user__email',)


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'email_notifications_enabled',
		'push_notifications_enabled',
		'auto_reply_enabled',
		'file_sharing_enabled',
		'video_calls_enabled',
		'screen_sharing_enabled',
	)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'notification_type', 'title', 'is_read', 'created_at')
	list_filter = ('notification_type', 'is_read', 'created_at')
	search_fields = ('user__email', 'title', 'body')
