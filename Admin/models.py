from django.db import models

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
    
    def save(self, *args, **kwargs):
        # Ensure the associated user has the 'admin' role
        if self.user.role and self.user.role.name != 'admin':
            raise ValueError("Associated user must have the 'admin' role.")
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