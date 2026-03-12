from django.contrib import admin

# Register your models here.
from .models import Channel, Workspace

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'slug', 'created_at', 'updated_at')
    search_fields = ('name', 'type')
    list_filter = ('type', 'created_at')
    readonly_fields = ('slug',)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_filter = ('created_at',)
    readonly_fields = ('slug',)
