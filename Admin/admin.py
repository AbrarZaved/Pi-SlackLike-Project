from django.contrib import admin

# Register your models here.
from .models import AdminProfile

@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'location', 'created_at')
    search_fields = ('user__email', 'department', 'location')
    list_filter = ('department', 'location', 'created_at')