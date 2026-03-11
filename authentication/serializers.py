"""
Serializers for Authentication APIs
"""

from rest_framework import serializers
from .models import User, Role, Permission


# ====================
# OTP Serializers
# ====================

class SendOTPSerializer(serializers.Serializer):
    """
    Serializer for sending OTP to user's email.
    User will be auto-created if doesn't exist.
    """
    email = serializers.EmailField(
        required=True,
        help_text="Email address to send OTP to"
    )


class VerifyOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying OTP.
    """
    email = serializers.EmailField(
        required=True,
        help_text="Email address of the user"
    )
    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
        help_text="6-digit OTP code"
    )
    
    def validate_email(self, value):
        """
        Validate that the email exists in the system.
        """
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist")
        return value
    
    def validate_otp(self, value):
        """
        Validate OTP format (must be 6 digits).
        """
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value


class LoginResponseSerializer(serializers.Serializer):
    """
    Serializer for OTP login response with JWT tokens.
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = serializers.DictField()

class AdminLoginSerializer(serializers.Serializer):
    """
    Serializer for admin login using email and password.
    """
    email = serializers.EmailField(
        required=True,
        help_text="Admin's email address"
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        help_text="Admin's password"
    )
    

# ====================
# User Serializers
# ====================

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    """
    role_name = serializers.CharField(source='role.name', read_only=True)
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'phone_number', 'title', 
            'profile_picture', 'status', 'role', 'role_name',
            'is_verified', 'created_at', 'updated_at', 'permissions'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_verified']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def get_permissions(self, obj):
        """Get list of permission codenames for the user."""
        if obj.role:
            return list(obj.role.permissions.values_list('codename', flat=True))
        return []


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new user.
    """
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['name', 'email', 'phone_number', 'password', 'title', 'role']
    
    def create(self, validated_data):
        """
        Create a new user with hashed password.
        """
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


# ====================
# Role Serializers
# ====================

class PermissionSerializer(serializers.ModelSerializer):
    """
    Serializer for Permission model.
    """
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'category', 'category_display', 'description']


class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer for Role model.
    """
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'slug', 'description', 
            'is_system_role', 'permissions', 'permission_count',
            'user_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_permission_count(self, obj):
        """Get the number of permissions assigned to this role."""
        return obj.permissions.count()
    
    def get_user_count(self, obj):
        """Get the number of users with this role."""
        return obj.users.count()


class RoleCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating roles with permission assignment.
    """
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of permission IDs to assign to this role"
    )
    
    class Meta:
        model = Role
        fields = ['name', 'slug', 'description', 'is_system_role', 'permission_ids']
    
    def create(self, validated_data):
        """
        Create a new role and assign permissions.
        """
        permission_ids = validated_data.pop('permission_ids', [])
        role = Role.objects.create(**validated_data)
        
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
        
        return role
    
    def update(self, instance, validated_data):
        """
        Update role and its permissions.
        """
        permission_ids = validated_data.pop('permission_ids', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update permissions if provided
        if permission_ids is not None:
            permissions = Permission.objects.filter(id__in=permission_ids)
            instance.permissions.set(permissions)
        
        return instance


# ====================
# Profile Update Serializers
# ====================

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for users to update their own profile.
    Regular users can update: name, phone_number, title, profile_picture, status
    """
    class Meta:
        model = User
        fields = ['name', 'phone_number', 'title', 'profile_picture', 'status']
        extra_kwargs = {
            'name': {'required': False},
            'phone_number': {'required': False},
            'title': {'required': False},
            'profile_picture': {'required': False},
            'status': {'required': False},
        }
    
    def validate_phone_number(self, value):
        """
        Validate that phone number is unique (if provided).
        """
        if value:
            user = self.instance
            if User.objects.filter(phone_number=value).exclude(id=user.id).exists():
                raise serializers.ValidationError("This phone number is already in use.")
        return value
    
    def validate_status(self, value):
        """
        Validate status field.
        """
        valid_statuses = ['active', 'inactive', 'away', 'busy']
        if value and value not in valid_statuses:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        return value
    
    def update(self, instance, validated_data):
        """
        Update user profile fields.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for admins to update their own profile.
    Admins can update same fields as regular users: name, phone_number, title, profile_picture
    """
    class Meta:
        model = User
        fields = ['name', 'phone_number', 'title', 'profile_picture', 'status']
        extra_kwargs = {
            'name': {'required': False},
            'phone_number': {'required': False},
            'title': {'required': False},
            'profile_picture': {'required': False},
            'status': {'required': False},
        }
    
    def validate_phone_number(self, value):
        """
        Validate that phone number is unique (if provided).
        """
        if value:
            user = self.instance
            if User.objects.filter(phone_number=value).exclude(id=user.id).exists():
                raise serializers.ValidationError("This phone number is already in use.")
        return value
    
    def validate_status(self, value):
        """
        Validate status field.
        """
        valid_statuses = ['active', 'inactive', 'away', 'busy']
        if value and value not in valid_statuses:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        return value
    
    def update(self, instance, validated_data):
        """
        Update admin profile fields.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
