from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count
from .models import User, Role, Permission, RolePermission


# ====================
# Permission Admin
# ====================
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing permissions.
    """
    list_display = ('codename', 'name', 'category', 'role_count', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('codename', 'name', 'description')
    ordering = ('category', 'codename')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Permission Details', {
            'fields': ('codename', 'name', 'category', 'description')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def role_count(self, obj):
        """Display the number of roles that have this permission."""
        count = obj.roles.count()
        return format_html(
            '<span style="color: #007bff; font-weight: bold;">{}</span>',
            count
        )
    role_count.short_description = 'Assigned to Roles'
    
    def get_queryset(self, request):
        """Optimize queryset with role counts."""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _role_count=Count('roles', distinct=True)
        )


# ====================
# RolePermission Inline
# ====================
class RolePermissionInline(admin.TabularInline):
    """
    Inline admin for managing role permissions.
    Allows adding/removing permissions directly from Role admin.
    """
    model = RolePermission
    extra = 1
    autocomplete_fields = ['permission']
    readonly_fields = ('granted_at',)
    
    def get_queryset(self, request):
        """Order permissions by category and codename."""
        queryset = super().get_queryset(request)
        return queryset.select_related('permission').order_by(
            'permission__category',
            'permission__codename'
        )


# ====================
# Role Admin
# ====================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin interface for managing roles and their permissions.
    """
    list_display = (
        'name', 
        'slug', 
        'permission_count', 
        'user_count',
        'is_system_role',
        'created_at'
    )
    list_filter = ('is_system_role', 'created_at')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at', 'permission_list')
    inlines = [RolePermissionInline]
    
    fieldsets = (
        ('Role Information', {
            'fields': ('name', 'slug', 'description', 'is_system_role')
        }),
        ('Permissions Summary', {
            'fields': ('permission_list',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def permission_count(self, obj):
        """Display the number of permissions assigned to this role."""
        count = obj.permissions.count()
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">{} permissions</span>',
            count
        )
    permission_count.short_description = 'Permissions'
    
    def user_count(self, obj):
        """Display the number of users with this role."""
        count = obj.users.count()
        return format_html(
            '<span style="background-color: #007bff; color: white; padding: 3px 8px; border-radius: 3px;">{} users</span>',
            count
        )
    user_count.short_description = 'Users'
    
    def permission_list(self, obj):
        """Display a formatted list of all permissions for this role."""
        if not obj.pk:
            return "Save the role first to see permissions."
        
        permissions = obj.permissions.all().order_by('category', 'codename')
        if not permissions:
            return "No permissions assigned yet."
        
        # Group permissions by category
        categories = {}
        for perm in permissions:
            category_name = perm.get_category_display()
            if category_name not in categories:
                categories[category_name] = []
            categories[category_name].append(perm)
        
        # Build HTML
        html = '<div style="margin-top: 10px;">'
        for category, perms in categories.items():
            html += f'<h4 style="color: #007bff; margin-top: 15px;">{category}</h4>'
            html += '<ul style="margin-left: 20px;">'
            for perm in perms:
                html += f'<li><strong>{perm.codename}</strong> - {perm.name}</li>'
            html += '</ul>'
        html += '</div>'
        
        return mark_safe(html)
    permission_list.short_description = 'All Permissions'
    
    def get_queryset(self, request):
        """Optimize queryset with counts."""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _permission_count=Count('permissions', distinct=True),
            _user_count=Count('users', distinct=True)
        )
    
    def delete_queryset(self, request, queryset):
        """Prevent deletion of system roles."""
        system_roles = queryset.filter(is_system_role=True)
        if system_roles.exists():
            self.message_user(
                request,
                f"Cannot delete system roles: {', '.join(system_roles.values_list('name', flat=True))}",
                level='error'
            )
            queryset = queryset.filter(is_system_role=False)
        super().delete_queryset(request, queryset)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of system roles."""
        if obj and obj.is_system_role:
            return False
        return super().has_delete_permission(request, obj)


# ====================
# User Admin
# ====================
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Admin interface for managing users with role-based permissions.
    """
    list_display = (
        'email',
        'name',
        'phone_number', 
        'role_display',
        'status',
        'permission_count',
        'created_at'
    )
    list_filter = ('status', 'role', 'created_at')
    search_fields = ('email', 'name', 'phone_number', 'title')
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'user_permissions_display', 'password')
    autocomplete_fields = ['role']
    
    fieldsets = (
        ('User Information', {
            'fields': ('name', 'email', 'phone_number', 'title', 'slug')
        }),
        ('Authentication', {
            'fields': ('password', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'user_permissions_display')
        }),
        ('Profile', {
            'fields': ('profile_picture', 'status')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_login'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('User Information', {
            'fields': ('name', 'email', 'phone_number', 'password')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Override save to handle password hashing."""
        if not change:  # Creating new user
            # Password will be in plain text from form
            if obj.password and not obj.password.startswith('pbkdf2_'):
                obj.set_password(obj.password)
        super().save_model(request, obj, form, change)
    
    def get_fieldsets(self, request, obj=None):
        """Use add_fieldsets when creating a new user."""
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent users from deleting themselves."""
        if obj and obj == request.user:
            return False
        return super().has_delete_permission(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Prevent users from deleting themselves in bulk actions."""
        if request.user in queryset:
            self.message_user(
                request,
                "You cannot delete your own account.",
                level='error'
            )
            queryset = queryset.exclude(pk=request.user.pk)
        super().delete_queryset(request, queryset)
    
    def role_display(self, obj):
        """Display user's role with formatting."""
        if obj.role:
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
                obj.role.name
            )
        return format_html(
            '<span style="color: #dc3545;">{}</span>',
            'No Role'
        )
    role_display.short_description = 'Role'
    
    def permission_count(self, obj):
        """Display the number of permissions user has through their role."""
        if not obj.role:
            return format_html('<span style="color: #dc3545;">{}</span>', 0)
        count = obj.role.permissions.count()
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">{}</span>',
            count
        )
    permission_count.short_description = 'Permissions'
    
    def user_permissions_display(self, obj):
        """Display all permissions the user has through their role."""
        if not obj.role:
            return "No role assigned - user has no permissions."
        
        permissions = obj.get_all_permissions().order_by('category', 'codename')
        if not permissions:
            return "Role has no permissions assigned."
        
        # Group by category
        categories = {}
        for perm in permissions:
            category_name = perm.get_category_display()
            if category_name not in categories:
                categories[category_name] = []
            categories[category_name].append(perm)
        
        # Build HTML
        html = f'<div style="margin-top: 10px;"><p><strong>Role:</strong> {obj.role.name}</p>'
        for category, perms in categories.items():
            html += f'<h4 style="color: #007bff; margin-top: 15px;">{category}</h4>'
            html += '<ul style="margin-left: 20px;">'
            for perm in perms:
                html += f'<li><code>{perm.codename}</code> - {perm.name}</li>'
            html += '</ul>'
        html += '</div>'
        
        return mark_safe(html)
    user_permissions_display.short_description = 'User Permissions'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        queryset = super().get_queryset(request)
        return queryset.select_related('role')


# ====================
# RolePermission Admin
# ====================
@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """
    Admin interface for RolePermission through model.
    Provides a direct view of role-permission assignments.
    """
    list_display = ('role', 'permission', 'permission_category', 'granted_at')
    list_filter = ('role', 'permission__category', 'granted_at')
    search_fields = ('role__name', 'permission__codename', 'permission__name')
    autocomplete_fields = ['role', 'permission']
    readonly_fields = ('granted_at',)
    
    def permission_category(self, obj):
        """Display the permission category."""
        return obj.permission.get_category_display()
    permission_category.short_description = 'Category'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        queryset = super().get_queryset(request)
        return queryset.select_related('role', 'permission')
