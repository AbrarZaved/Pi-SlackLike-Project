from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


# ====================
# User Manager
# ====================
class UserManager(BaseUserManager):
    """
    Custom manager for the User model.
    Handles user creation and natural key lookup.
    """
    def get_by_natural_key(self, email):
        """
        Get user by their natural key (email).
        Required for Django authentication.
        """
        return self.get(**{self.model.USERNAME_FIELD: email})
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        Automatically assigns 'Customer' role if no role is provided.
        """
        if not email:
            raise ValueError('The Email field must be set')
        
        # Assign default Customer role if not provided
        if 'role' not in extra_fields or extra_fields.get('role') is None:
            from django.db.models import Q
            try:
                customer_role = Role.objects.get(Q(slug='customer') | Q(name__iexact='customer'))
                extra_fields['role'] = customer_role
            except Role.DoesNotExist:
                # Customer role will be created by seed_permissions command
                pass
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        # Get or create Admin role for superuser
        from django.db.models import Q
        
        # Try to find an Admin role
        try:
            admin_role = Role.objects.get(Q(slug='admin') | Q(name__iexact='admin'))
        except Role.DoesNotExist:
            # Create basic admin role if it doesn't exist
            admin_role = Role.objects.create(
                name='Admin',
                slug='admin',
                description='Administrator with full access',
                is_system_role=True
            )
        
        extra_fields.setdefault('role', admin_role)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        return self.create_user(email, password, **extra_fields)


# ====================
# Permission Model
# ====================
class Permission(models.Model):
    """
    Represents a specific permission in the system.
    Permissions are organized into logical categories.
    """
    CATEGORY_CHOICES = (
        ('user_management', 'User Management'),
        ('communication', 'Communication'),
        ('channels', 'Channels'),
        ('files', 'Files'),
        ('notifications', 'Notifications'),
    )
    
    codename = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Unique identifier for the permission (e.g., 'send_receive_messages')"
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for the permission"
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        help_text="Logical category this permission belongs to"
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'codename']
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return f"{self.name} ({self.codename})"


# ====================
# Role Model
# ====================
class Role(models.Model):
    """
    Represents a role in the system.
    Each role can have multiple permissions.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Role name (e.g., 'Admin', 'Team Member')"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly identifier for the role"
    )
    description = models.TextField(blank=True, null=True)
    permissions = models.ManyToManyField(
        Permission,
        through='RolePermission',
        related_name='roles',
        blank=True
    )
    is_system_role = models.BooleanField(
        default=False,
        help_text="System roles cannot be deleted"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.name
    
    def has_permission(self, permission_codename):
        """
        Check if this role has a specific permission.
        
        Args:
            permission_codename (str): The permission codename to check
            
        Returns:
            bool: True if role has the permission, False otherwise
        """
        return self.permissions.filter(codename=permission_codename).exists()


# ====================
# RolePermission (Through Model)
# ====================
class RolePermission(models.Model):
    """
    Intermediate model for Role-Permission many-to-many relationship.
    Allows for additional metadata about permission assignments.
    """
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='permission_roles'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['role', 'permission']
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
    
    def __str__(self):
        return f"{self.role.name} - {self.permission.codename}"


# ====================
# User Model
# ====================
class User(AbstractBaseUser):
    """
    Custom user model with role-based access control.
    Each user is assigned one role.
    """
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True,
        help_text="The role assigned to this user"
    )
    name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Full name of the user"
    )
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        null=True, 
        blank=True
    )
    title = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=15, 
        unique=True,
        null=True,
        blank=True,
        help_text="Phone number (optional)"
    )
    status = models.CharField(max_length=20, default='active')
    slug = models.SlugField(null=True, blank=True)
    
    # OTP Fields
    otp = models.CharField(
        max_length=6, 
        null=True, 
        blank=True,
        help_text="One-Time Password for authentication"
    )
    otp_created_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when OTP was generated"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether user has verified their email via OTP"
    )
    
    # Django admin fields
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this user should be treated as active"
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into the admin site"
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="Designates that this user has all permissions"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Custom manager
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email
    
    def natural_key(self):
        """
        Return the natural key for this user (email).
        Required for Django serialization and authentication.
        """
        return (self.email,)
    
    # Django Admin Permission Methods
    def has_perm(self, perm, obj=None):
        """
        Check if user has a specific permission.
        Required for Django admin.
        """
        if self.is_superuser:
            return True
        # Extract codename from permission string (e.g., 'app.permission_name' -> 'permission_name')
        if '.' in perm:
            perm = perm.split('.')[-1]
        return self.has_permission(perm)
    
    def has_module_perms(self, app_label):
        """
        Check if user has permissions to view the app.
        Required for Django admin.
        """
        if self.is_superuser or self.is_staff:
            return True
        return False
    
    def has_permission(self, permission_codename):
        """
        Check if this user has a specific permission through their role.
        
        Args:
            permission_codename (str): The permission codename to check
            
        Returns:
            bool: True if user has the permission, False otherwise
        """
        if not self.role:
            return False
        return self.role.has_permission(permission_codename)
    
    def get_all_permissions(self):
        """
        Get all permissions for this user based on their role.
        
        Returns:
            QuerySet: All permissions for the user's role
        """
        if not self.role:
            return Permission.objects.none()
        return self.role.permissions.all()
    
    @property
    def role_name(self):
        """Get the name of the user's role."""
        return self.role.name if self.role else None
    
    def generate_otp(self):
        """
        Generate a 6-digit OTP and store it with timestamp.
        
        Returns:
            str: The generated OTP
        """
        import random
        from django.utils import timezone
        
        otp = str(random.randint(100000, 999999))
        self.otp = otp
        self.otp_created_at = timezone.now()
        self.save()
        return otp
    
    def verify_otp(self, otp_input):
        """
        Verify the provided OTP.
        OTP is valid for 10 minutes.
        
        Args:
            otp_input (str): The OTP to verify
            
        Returns:
            tuple: (bool, str) - (is_valid, message)
        """
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.otp:
            return False, "No OTP generated for this user"
        
        if self.otp != otp_input:
            return False, "Invalid OTP"
        
        # Check if OTP is expired (10 minutes validity)
        if self.otp_created_at:
            expiry_time = self.otp_created_at + timedelta(minutes=10)
            if timezone.now() > expiry_time:
                return False, "OTP has expired"
        
        # OTP is valid - clear it after verification
        self.otp = None
        self.otp_created_at = None
        self.save()
        return True, "OTP verified successfully"