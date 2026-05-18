from django.contrib import admin

# Register your models here.
from .models import AdminProfile, Miscellaneous

@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'location', 'created_at')
    search_fields = ('user__email', 'department', 'location')
    list_filter = ('department', 'location', 'created_at')


@admin.register(Miscellaneous)
class MiscellaneousAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'created_at')
    search_fields = ('key',)
    list_filter = ('created_at',)