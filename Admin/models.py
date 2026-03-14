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