from django.db import models
from django.utils.text import slugify
from django.conf import settings

# Create your models here.

class Channel(models.Model):
    
    CHANNEL_TYPES = (
        ('private', 'Private'),
        ('public', 'Public'),
    )

    name=models.CharField(max_length=255)
    type=models.CharField(max_length=20, choices=CHANNEL_TYPES)
    users=models.ManyToManyField('authentication.User', related_name='channels')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Channel'
        verbose_name_plural = 'Channels'
    
    def __str__(self):
        return self.name


class Workspace(models.Model):
    name=models.CharField(max_length=255)
    sharable_link=models.URLField(max_length=500, null=True, blank=True)
    picture=models.ImageField(upload_to='workspace_pictures/', null=True, blank=True)
    channels=models.ManyToManyField(Channel, related_name='workspaces', blank=True, null=True)
    users=models.ManyToManyField('authentication.User', related_name='workspaces', blank=True, null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Save first to get the ID
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Generate shareable link after we have an ID
        if is_new and not self.sharable_link:
            # Get base URL from allowed hosts
            allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
            if allowed_hosts and allowed_hosts[0] not in ['*', 'localhost', '127.0.0.1']:
                domain = allowed_hosts[0]
                protocol = 'https' if not settings.DEBUG else 'http'
                base_url = f"{protocol}://{domain}"
            else:
                # Fallback for development
                base_url = 'http://localhost:8000'
            
            workspace_slug = slugify(self.name)
            self.sharable_link = f"{base_url}/workspace/{workspace_slug}/{self.id}"
            # Save again to update the sharable_link
            super().save(update_fields=['sharable_link'])