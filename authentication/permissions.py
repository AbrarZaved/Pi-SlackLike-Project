"""
Custom Permission System for Django REST Framework
Implements role-based access control (RBAC) with dynamic permission checking.
"""

from rest_framework.permissions import BasePermission
from typing import Optional


# ====================
# Permission Constants
# ====================

class PermissionConstants:
    """
    Centralized permission constants organized by category.
    These match the codenames stored in the Permission model.
    """
    
    # User Management Permissions
    MANAGE_USERS = 'manage_users'
    MANAGE_CONTACTS = 'manage_contacts'
    
    # Communication Permissions
    SEND_RECEIVE_MESSAGES = 'send_receive_messages'
    CALLING = 'calling'
    
    # Channel Permissions
    CREATE_CHANNELS = 'create_channels'
    JOIN_CHANNELS = 'join_channels'
    
    # File Permissions
    UPLOAD_FILES = 'upload_files'
    SHARE_FILES = 'share_files'
    
    # Notification Permissions
    MANAGE_NOTIFICATIONS = 'manage_notifications'
    
    @classmethod
    def get_all_permissions(cls):
        """
        Get all permission constants as a list.
        
        Returns:
            list: List of all permission codenames
        """
        return [
            cls.MANAGE_USERS,
            cls.MANAGE_CONTACTS,
            cls.SEND_RECEIVE_MESSAGES,
            cls.CALLING,
            cls.CREATE_CHANNELS,
            cls.JOIN_CHANNELS,
            cls.UPLOAD_FILES,
            cls.SHARE_FILES,
            cls.MANAGE_NOTIFICATIONS,
        ]
    
    @classmethod
    def get_permissions_by_category(cls):
        """
        Get permissions organized by category.
        
        Returns:
            dict: Dictionary with categories as keys and permission lists as values
        """
        return {
            'user_management': [
                cls.MANAGE_USERS,
                cls.MANAGE_CONTACTS,
            ],
            'communication': [
                cls.SEND_RECEIVE_MESSAGES,
                cls.CALLING,
            ],
            'channels': [
                cls.CREATE_CHANNELS,
                cls.JOIN_CHANNELS,
            ],
            'files': [
                cls.UPLOAD_FILES,
                cls.SHARE_FILES,
            ],
            'notifications': [
                cls.MANAGE_NOTIFICATIONS,
            ],
        }


# ====================
# Custom DRF Permission Classes
# ====================

class HasPermission(BasePermission):
    """
    Custom DRF permission class that checks if a user has a specific permission.
    
    Usage:
        # In your view:
        from authentication.permissions import HasPermission
        
        class MessageViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, HasPermission("send_receive_messages")]
            ...
    
    Or for dynamic permission checking:
        class MessageViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, HasPermission]
            required_permission = "send_receive_messages"
            ...
    """
    
    def __init__(self, permission_codename: Optional[str] = None):
        """
        Initialize the permission class with an optional permission codename.
        
        Args:
            permission_codename (str, optional): The permission to check for
        """
        self.permission_codename = permission_codename
        super().__init__()
    
    def has_permission(self, request, view):
        """
        Check if the user has the required permission.
        
        Args:
            request: The Django request object
            view: The DRF view object
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get permission codename from init or view attribute
        permission_codename = self.permission_codename
        if not permission_codename and hasattr(view, 'required_permission'):
            permission_codename = view.required_permission
        
        if not permission_codename:
            # If no permission specified, deny access by default
            return False
        
        # Check if user has the permission
        return user_has_permission(request.user, permission_codename)


class IsAdmin(BasePermission):
    """
    Permission class that checks if user has an Admin role.
    
    Usage:
        class AdminOnlyView(APIView):
            permission_classes = [IsAuthenticated, IsAdmin]
            ...
    """
    
    def has_permission(self, request, view):
        """
        Check if the user is an admin.
        
        Args:
            request: The Django request object
            view: The DRF view object
            
        Returns:
            bool: True if user is admin, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not request.user.role:
            return False
        
        return request.user.role.slug == 'admin'


class HasAnyPermission(BasePermission):
    """
    Permission class that checks if user has at least one of the specified permissions.
    
    Usage:
        class FileViewSet(viewsets.ModelViewSet):
            permission_classes = [
                IsAuthenticated, 
                HasAnyPermission(["upload_files", "share_files"])
            ]
            ...
    """
    
    def __init__(self, permission_codenames: list):
        """
        Initialize with a list of permission codenames.
        
        Args:
            permission_codenames (list): List of permission codenames
        """
        self.permission_codenames = permission_codenames
        super().__init__()
    
    def has_permission(self, request, view):
        """
        Check if user has any of the required permissions.
        
        Args:
            request: The Django request object
            view: The DRF view object
            
        Returns:
            bool: True if user has at least one permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        for permission_codename in self.permission_codenames:
            if user_has_permission(request.user, permission_codename):
                return True
        
        return False


class HasAllPermissions(BasePermission):
    """
    Permission class that checks if user has all of the specified permissions.
    
    Usage:
        class AdvancedFeatureView(APIView):
            permission_classes = [
                IsAuthenticated,
                HasAllPermissions(["manage_users", "manage_contacts"])
            ]
            ...
    """
    
    def __init__(self, permission_codenames: list):
        """
        Initialize with a list of permission codenames.
        
        Args:
            permission_codenames (list): List of permission codenames
        """
        self.permission_codenames = permission_codenames
        super().__init__()
    
    def has_permission(self, request, view):
        """
        Check if user has all required permissions.
        
        Args:
            request: The Django request object
            view: The DRF view object
            
        Returns:
            bool: True if user has all permissions, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        for permission_codename in self.permission_codenames:
            if not user_has_permission(request.user, permission_codename):
                return False
        
        return True


# ====================
# Helper Utilities
# ====================

def user_has_permission(user, permission_codename: str) -> bool:
    """
    Check if a user has a specific permission.
    
    This is the core helper function used throughout the application
    to check permissions.
    
    Args:
        user: User instance
        permission_codename (str): The permission codename to check
        
    Returns:
        bool: True if user has the permission, False otherwise
        
    Usage:
        from authentication.permissions import user_has_permission
        
        if user_has_permission(request.user, "send_receive_messages"):
            # Allow action
            pass
    """
    if not user or not hasattr(user, 'role'):
        return False
    
    return user.has_permission(permission_codename)


def get_user_permissions(user) -> list:
    """
    Get all permissions for a user.
    
    Args:
        user: User instance
        
    Returns:
        list: List of permission codenames the user has
        
    Usage:
        from authentication.permissions import get_user_permissions
        
        permissions = get_user_permissions(request.user)
        # Returns: ['send_receive_messages', 'calling', 'join_channels']
    """
    if not user or not hasattr(user, 'role') or not user.role:
        return []
    
    return list(
        user.role.permissions.values_list('codename', flat=True)
    )


def check_multiple_permissions(user, permission_codenames: list, require_all: bool = False) -> bool:
    """
    Check if a user has multiple permissions.
    
    Args:
        user: User instance
        permission_codenames (list): List of permission codenames to check
        require_all (bool): If True, user must have all permissions. 
                          If False, user needs at least one.
        
    Returns:
        bool: True if condition met, False otherwise
        
    Usage:
        from authentication.permissions import check_multiple_permissions
        
        # User needs at least one permission
        has_any = check_multiple_permissions(
            request.user, 
            ["upload_files", "share_files"],
            require_all=False
        )
        
        # User needs all permissions
        has_all = check_multiple_permissions(
            request.user,
            ["manage_users", "manage_contacts"],
            require_all=True
        )
    """
    if not user or not hasattr(user, 'role'):
        return False
    
    if require_all:
        # User must have all permissions
        for permission_codename in permission_codenames:
            if not user_has_permission(user, permission_codename):
                return False
        return True
    else:
        # User needs at least one permission
        for permission_codename in permission_codenames:
            if user_has_permission(user, permission_codename):
                return True
        return False


def permission_required(permission_codename: str):
    """
    Decorator to check permissions in regular Django views or functions.
    
    Args:
        permission_codename (str): The permission codename required
        
    Returns:
        function: Decorated function
        
    Usage:
        from authentication.permissions import permission_required
        from django.http import HttpResponse
        
        @permission_required("manage_users")
        def admin_dashboard(request):
            return HttpResponse("Admin Dashboard")
    """
    from functools import wraps
    from django.core.exceptions import PermissionDenied
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not user_has_permission(request.user, permission_codename):
                raise PermissionDenied(
                    f"You don't have the required permission: {permission_codename}"
                )
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator
