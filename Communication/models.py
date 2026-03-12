from django.db import models
from django.utils.text import slugify
from django.conf import settings

# Create your models here.

class Channel(models.Model):
    
    CHANNEL_TYPES = (
        ('private', 'Private'),
        ('public', 'Public'),
    )
    user=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_channels', null=True, blank=True)
    name=models.CharField(max_length=255)
    type=models.CharField(max_length=20, choices=CHANNEL_TYPES)
    slug=models.SlugField(max_length=300, unique=True, null=True, blank=True)
    users=models.ManyToManyField('authentication.User', related_name='channels')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Channel'
        verbose_name_plural = 'Channels'
    
    def __str__(self):
        return self.name

    def generate_unique_slug(self):
        """Generate a unique slug for the channel"""
        base_slug = slugify(self.name)
        unique_slug = base_slug
        counter = 1
        
        while Channel.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
            unique_slug = f"{base_slug}-{counter}"
            counter += 1
        
        return unique_slug
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)


class Workspace(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_workspaces', null=True, blank=True)
    name=models.CharField(max_length=255)
    slug=models.SlugField(max_length=300, unique=True, null=True, blank=True)
    picture=models.ImageField(upload_to='workspace_pictures/', null=True, blank=True)
    channels=models.ManyToManyField(Channel, related_name='workspaces', blank=True)
    users=models.ManyToManyField('authentication.User', related_name='workspaces', blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return self.name
    
    def generate_unique_slug(self):
        """Generate a unique slug for the workspace"""
        base_slug = slugify(self.name)
        unique_slug = base_slug
        counter = 1
        
        while Workspace.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
            unique_slug = f"{base_slug}-{counter}"
            counter += 1
        
        return unique_slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)