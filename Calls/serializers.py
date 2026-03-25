from rest_framework import serializers

from .models import Call, CallParticipant


class CallParticipantSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = CallParticipant
        fields = ['user_id', 'email', 'name', 'joined_at', 'left_at']


class CallSerializer(serializers.ModelSerializer):
    participants = CallParticipantSerializer(many=True, read_only=True)
    created_by_id = serializers.IntegerField(source='created_by.id', read_only=True)

    class Meta:
        model = Call
        fields = [
            'id',
            'room_name',
            'title',
            'is_video',
            'is_active',
            'started_at',
            'ended_at',
            'context_type',
            'workspace_id',
            'channel_id',
            'dm_thread_id',
            'created_by_id',
            'participants',
        ]


class CreateCallSerializer(serializers.Serializer):
    context_type = serializers.ChoiceField(choices=Call.CONTEXT_TYPES)
    workspace_id = serializers.IntegerField(required=False)
    channel_id = serializers.IntegerField(required=False)
    dm_thread_id = serializers.IntegerField(required=False)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text='List of user IDs to invite (excluding self is allowed; self will be included automatically).'
    )
    title = serializers.CharField(required=False, allow_blank=True, default='')
    is_video = serializers.BooleanField(required=False, default=True)


class TokenResponseSerializer(serializers.Serializer):
    call_id = serializers.UUIDField()
    room_name = serializers.CharField()
    livekit_url = serializers.CharField()
    token = serializers.CharField()
    can_screen_share = serializers.BooleanField()


class CallSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    context_type = serializers.CharField()
    workspace_id = serializers.IntegerField(allow_null=True)
    channel_id = serializers.IntegerField(allow_null=True)
    dm_thread_id = serializers.IntegerField(allow_null=True)
    title = serializers.CharField(allow_blank=True)
    room_name = serializers.CharField()
    is_video = serializers.BooleanField()
    is_active = serializers.BooleanField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.IntegerField(allow_null=True)
    total_participants = serializers.IntegerField()
    joined_participants = serializers.IntegerField()
    left_participants = serializers.IntegerField()
    active_participants = serializers.IntegerField()
    participants = CallParticipantSerializer(many=True)


class CallLogListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    context_type = serializers.CharField()
    workspace_id = serializers.IntegerField(allow_null=True)
    channel_id = serializers.IntegerField(allow_null=True)
    dm_thread_id = serializers.IntegerField(allow_null=True)
    title = serializers.CharField(allow_blank=True)
    is_video = serializers.BooleanField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.IntegerField(allow_null=True)
    total_participants = serializers.IntegerField()
