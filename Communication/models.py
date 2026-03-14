from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.db.models import Q

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
    is_active=models.BooleanField(default=True)
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
    is_active=models.BooleanField(default=True)
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

    
class Group(models.Model):
    
    user=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_groups', null=True, blank=True)
    name=models.CharField(max_length=255)
    slug=models.SlugField(max_length=300, unique=True, null=True, blank=True)
    group_admin=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_groups', null=True, blank=True)
    group_picture=models.ImageField(upload_to='group_pictures/', null=True, blank=True)
    users=models.ManyToManyField('authentication.User', related_name='groups', blank=True)
    is_active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'

    def __str__(self):
        return self.name

    def generate_unique_slug(self):
        """Generate a unique slug for the group"""
        base_slug = slugify(self.name)
        unique_slug = base_slug
        counter = 1
        
        while Group.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
            unique_slug = f"{base_slug}-{counter}"
            counter += 1
        
        return unique_slug
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)


class DirectMessageThread(models.Model):
    """1:1 direct message thread between two users."""

    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dm_threads_as_a'
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dm_threads_as_b'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user_a', 'user_b'], name='unique_dm_thread_pair'),
            models.CheckConstraint(condition=~Q(user_a=models.F('user_b')), name='dm_thread_users_distinct'),
        ]

    def save(self, *args, **kwargs):
        # Ensure deterministic ordering so (a,b) and (b,a) map to same row.
        if self.user_a_id and self.user_b_id and self.user_a_id > self.user_b_id:
            self.user_a_id, self.user_b_id = self.user_b_id, self.user_a_id
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_for_users(cls, user1, user2):
        user_a, user_b = (user1, user2) if user1.id <= user2.id else (user2, user1)
        thread, _ = cls.objects.get_or_create(user_a=user_a, user_b=user_b)
        return thread


class ChatMessage(models.Model):
    """Chat message that belongs to exactly one of: channel, group, or DM thread."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True
    )
    dm_thread = models.ForeignKey(
        DirectMessageThread,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True
    )
    content = models.TextField(blank=True, null=True)
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='replies',
        null=True,
        blank=True
    )
    forwarded_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='forwards',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                name='chatmessage_exactly_one_target',
                condition=(
                    (
                        Q(channel__isnull=False, group__isnull=True, dm_thread__isnull=True)
                        | Q(channel__isnull=True, group__isnull=False, dm_thread__isnull=True)
                        | Q(channel__isnull=True, group__isnull=True, dm_thread__isnull=False)
                    )
                ),
            ),
        ]

    def __str__(self):
        return f"Message {self.pk} from {self.sender_id}"


class ChatReaction(models.Model):
    """Reaction on a chat message."""

    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_reactions'
    )
    emoji = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['message', 'user', 'emoji'], name='unique_reaction_per_user'),
        ]

    def __str__(self):
        return f"{self.emoji} on {self.message_id} by {self.user_id}"