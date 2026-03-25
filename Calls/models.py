from uuid import uuid4

from django.conf import settings
from django.db import models


class Call(models.Model):
	"""Represents a LiveKit room session within a workspace/channel/DM context."""

	CONTEXT_TYPES = (
		('workspace', 'Workspace'),
		('channel', 'Channel'),
		('dm', 'Direct Message'),
	)

	id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
	room_name = models.CharField(max_length=128, unique=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='created_calls',
	)

	context_type = models.CharField(max_length=20, choices=CONTEXT_TYPES)
	workspace = models.ForeignKey(
		'Communication.Workspace',
		on_delete=models.CASCADE,
		null=True,
		blank=True,
		related_name='calls',
	)
	channel = models.ForeignKey(
		'Communication.Channel',
		on_delete=models.CASCADE,
		null=True,
		blank=True,
		related_name='calls',
	)
	dm_thread = models.ForeignKey(
		'Communication.DirectMessageThread',
		on_delete=models.CASCADE,
		null=True,
		blank=True,
		related_name='calls',
	)

	title = models.CharField(max_length=255, blank=True, default='')
	is_video = models.BooleanField(default=True)
	is_active = models.BooleanField(default=True)
	started_at = models.DateTimeField(auto_now_add=True)
	ended_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		indexes = [
			models.Index(fields=['context_type', 'is_active']),
			models.Index(fields=['started_at']),
		]

	def __str__(self) -> str:
		return f"Call {self.id} ({self.room_name})"


class CallParticipant(models.Model):
	"""Participant membership for a call session."""

	call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='participants')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='call_participations')
	invited_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='sent_call_invites',
	)
	joined_at = models.DateTimeField(null=True, blank=True)
	left_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['call', 'user'], name='unique_call_participant'),
		]

	def __str__(self) -> str:
		return f"{self.user_id} in {self.call_id}"

# Create your models here.
