from django.db import models
from django.core.exceptions import ValidationError

# Create your models here.

class AdminProfile(models.Model):
    user=models.OneToOneField('authentication.User', on_delete=models.CASCADE, related_name='admin_profile')
    bio=models.TextField(blank=True, null=True)
    department=models.CharField(max_length=100, blank=True, null=True)
    location=models.CharField(max_length=100, blank=True, null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AdminProfile for {self.user.email}"

    @staticmethod
    def _role_is_admin(role) -> bool:
        if not role:
            return False
        slug = getattr(role, 'slug', None)
        name = getattr(role, 'name', None)
        if isinstance(slug, str) and slug.lower() == 'admin':
            return True
        if isinstance(name, str) and name.lower() == 'admin':
            return True
        return False

    def clean(self):
        super().clean()

        # Keep prior behavior: only enforce if a role exists.
        # (This avoids breaking environments where role can be null.)
        if self.user_id and getattr(self.user, 'role', None):
            if not self._role_is_admin(self.user.role):
                raise ValidationError({'user': "Associated user must have the 'admin' role."})

    def save(self, *args, **kwargs):
        # Ensure model validation errors show up in Django admin forms
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Admin Profile'
        verbose_name_plural = 'Admin Profiles'


class Miscellaneous(models.Model):
    key=models.CharField(max_length=100, unique=True)
    value=models.TextField(blank=True, null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

    class Meta:
        verbose_name = 'Miscellaneous'
        verbose_name_plural = 'Miscellaneous'


class Automation(models.Model):
    TRIGGER_USER_JOINS = 'user_joins'
    TRIGGER_NEW_MESSAGE = 'new_message'
    TRIGGER_CHOICES = (
        (TRIGGER_USER_JOINS, 'User Joins'),
        (TRIGGER_NEW_MESSAGE, 'New Message'),
    )

    ACTION_SEND_MESSAGE = 'send_message'
    ACTION_SEND_EMAIL = 'send_email'
    ACTION_CHOICES = (
        (ACTION_SEND_MESSAGE, 'Send Message'),
        (ACTION_SEND_EMAIL, 'Send Email'),
    )

    name = models.CharField(max_length=255)
    workspace = models.ForeignKey(
        'Communication.Workspace',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='automations',
        help_text='If set, automation only applies to this workspace. Otherwise applies to all workspaces.'
    )
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    message_content = models.TextField(blank=True, null=True)
    email_subject = models.CharField(max_length=255, blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_automations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Automation'
        verbose_name_plural = 'Automations'

    def __str__(self):
        return self.name


class AutomationExecution(models.Model):
    automation = models.ForeignKey(
        Automation,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    workspace = models.ForeignKey(
        'Communication.Workspace',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automation_executions'
    )
    channel = models.ForeignKey(
        'Communication.Channel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automation_executions'
    )
    message = models.ForeignKey(
        'Communication.ChatMessage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automation_executions'
    )
    target_user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automation_executions'
    )
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Automation Execution'
        verbose_name_plural = 'Automation Executions'
        ordering = ['-created_at']