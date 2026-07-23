"""
Serializers for Communication APIs
"""

from rest_framework import serializers
from .models import Channel, Workspace, Group, ChatMessage, ChatReaction, DirectMessageThread, ChatAttachment
from authentication.models import User


# ====================
# Channel Serializers
# ====================

class ChannelUserSerializer(serializers.ModelSerializer):
    """Serializer for users in a channel - minimal info"""
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'phone_number']
        read_only_fields = ['id', 'email', 'name', 'phone_number']


class CreatorSerializer(serializers.ModelSerializer):
    """Serializer for creator/owner user info"""
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'profile_picture']
        read_only_fields = ['id', 'email', 'name','profile_picture']

    def get_profile_picture(self, obj: User):
        if not getattr(obj, 'profile_picture', None):
            return None
        request = self.context.get('request')
        url = obj.profile_picture.url
        return request.build_absolute_uri(url) if request else url


class ChannelSerializer(serializers.ModelSerializer):
    """Serializer for Channel model"""
    created_by = CreatorSerializer(source='user', read_only=True)
    users = ChannelUserSerializer(many=True, read_only=True)
    user_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        source='users'
    )
    workspace_id = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(),
        write_only=True,
        required=False,
        source='workspace'
    )
    users_count = serializers.SerializerMethodField()
    shareable_url = serializers.SerializerMethodField()
    workspaces_info = serializers.SerializerMethodField()
    call_id = serializers.SerializerMethodField()
    call_token = serializers.SerializerMethodField()
    token = serializers.SerializerMethodField()
    livekit_url = serializers.SerializerMethodField()
    can_screen_share = serializers.SerializerMethodField()
    call_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Channel
        fields = [
            'id',
            'name',
            'type',
            'slug',
            'is_active',
            'shareable_url',
            'workspaces_info',
            'created_by',
            'users',
            'user_ids',
            'workspace_id',
            'users_count',
            'call_id',
            'call_token',
            'token',
            'livekit_url',
            'can_screen_share',
            'call_details',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'shareable_url', 'workspaces_info', 'created_by',
            'created_at', 'updated_at', 'call_id', 'call_token', 'token',
            'livekit_url', 'can_screen_share', 'call_details'
        ]




    def validate(self, attrs):
        """Ensure workspace is provided for channel creation."""
        if self.instance is None:
            workspace = attrs.get('workspace') or self.context.get('workspace')
            if workspace is None:
                raise serializers.ValidationError({
                    'workspace_id': 'workspace_id query param is required to create a channel.'
                })
            attrs['workspace'] = workspace
        else:
            attrs.pop('workspace', None)
        return attrs

    def create(self, validated_data):
        workspace = validated_data.pop('workspace', None) or self.context.get('workspace')
        users = validated_data.pop('users', [])

        channel = Channel.objects.create(**validated_data)
        if users:
            channel.users.add(*users)
        if workspace:
            workspace.channels.add(channel)

        return channel
    
    def get_users_count(self, obj):
        """Get the count of users in the channel"""
        return obj.users.count()
    
    def get_workspaces_info(self, obj):
        """Get list of workspaces this channel belongs to with shareable URLs"""
        request = self.context.get('request')
        workspaces_data = []
        
        for workspace in obj.workspaces.all():
            workspace_info = {
                'id': workspace.id,
                'name': workspace.name,
                'slug': workspace.slug,
            }
            if request:
                workspace_info['shareable_url'] = request.build_absolute_uri(
                    f'/api/v1/communication/workspaces/{workspace.slug}/channels/join/{obj.slug}/'
                )
            workspaces_data.append(workspace_info)
        
        return workspaces_data
    
    def get_shareable_url(self, obj):
        """Generate the shareable URL for the channel"""
        if obj.slug:
            request = self.context.get('request')
            # Get the workspace context if available
            workspace = self.context.get('workspace')
            if request and workspace:
                return request.build_absolute_uri(
                    f'/api/v1/communication/workspaces/{workspace.slug}/channels/join/{obj.slug}/'
                )
            elif request:
                # Fallback: return first workspace this channel belongs to
                first_workspace = obj.workspaces.first()
                if first_workspace:
                    return request.build_absolute_uri(
                        f'/api/v1/communication/workspaces/{first_workspace.slug}/channels/join/{obj.slug}/'
                    )
        return None

    def _get_channel_call_data(self, obj):
        """Helper to compute LiveKit call data for a channel."""
        request = self.context.get('request')
        if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
            return None

        from authentication.permissions import PermissionConstants, user_has_permission
        if not user_has_permission(request.user, PermissionConstants.CALLING):
            return None

        from Calls.models import Call
        from Calls.services.livekit import build_livekit_token
        from django.conf import settings

        active_call = Call.objects.filter(channel=obj, is_active=True).first()
        room_name = active_call.room_name if active_call else f"channel_{obj.id}"
        call_id = str(active_call.id) if active_call else None

        can_screen_share = user_has_permission(request.user, PermissionConstants.SCREEN_SHARE)

        try:
            token_result = build_livekit_token(
                user=request.user,
                room_name=room_name,
                can_publish=True,
                can_subscribe=True,
                can_screen_share=can_screen_share,
            )
            return {
                'call_id': call_id,
                'room_name': room_name,
                'livekit_url': getattr(settings, 'LIVEKIT_URL', ''),
                'token': token_result.token,
                'can_screen_share': token_result.can_screen_share,
                'is_active': bool(active_call),
            }
        except Exception:
            return None

    def get_call_id(self, obj):
        data = self._get_channel_call_data(obj)
        return data.get('call_id') if data else None

    def get_call_token(self, obj):
        data = self._get_channel_call_data(obj)
        return data.get('token') if data else None

    def get_token(self, obj):
        data = self._get_channel_call_data(obj)
        return data.get('token') if data else None

    def get_livekit_url(self, obj):
        data = self._get_channel_call_data(obj)
        return data.get('livekit_url') if data else ''

    def get_can_screen_share(self, obj):
        data = self._get_channel_call_data(obj)
        return data.get('can_screen_share') if data else False

    def get_call_details(self, obj):
        return self._get_channel_call_data(obj)





class ChannelListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing channels"""
    created_by = CreatorSerializer(source='user', read_only=True)
    users_count = serializers.SerializerMethodField()
    messages_count = serializers.IntegerField(read_only=True)
    workspaces = serializers.SerializerMethodField()
    
    class Meta:
        model = Channel
        fields = ['id', 'name', 'type', 'created_by', 'is_active', 'users_count', 'messages_count', 'workspaces', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']
    
    def get_users_count(self, obj):
        return obj.users.count()

    def get_workspaces(self, obj):
        return [{'id': ws.id, 'name': ws.name} for ws in obj.workspaces.all()]


class AddRemoveUsersSerializer(serializers.Serializer):
    """Serializer for adding/removing users to/from channels or workspaces"""
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text="List of user IDs to add or remove"
    )
    
    def validate_user_ids(self, value):
        """Validate that all user IDs exist"""
        if not value:
            raise serializers.ValidationError("At least one user ID is required")
        
        existing_users = User.objects.filter(id__in=value).values_list('id', flat=True)
        missing_ids = set(value) - set(existing_users)
        
        if missing_ids:
            raise serializers.ValidationError(
                f"Users with IDs {list(missing_ids)} do not exist"
            )
        
        return value


# ====================
# Workspace Serializers
# ====================

class WorkspaceChannelSerializer(serializers.ModelSerializer):
    """Serializer for channels in a workspace - minimal info"""
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Channel
        fields = ['id', 'name', 'type', 'users_count']
        read_only_fields = ['id', 'name', 'type', 'users_count']
    
    def get_users_count(self, obj):
        return obj.users.count()


class WorkspaceUserSerializer(serializers.ModelSerializer):
    """Serializer for users in a workspace - minimal info"""
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'phone_number']
        read_only_fields = ['id', 'email', 'name', 'phone_number']


class WorkspaceSerializer(serializers.ModelSerializer):
    """Serializer for Workspace model"""
    created_by = CreatorSerializer(source='user', read_only=True)
    channels = WorkspaceChannelSerializer(many=True, read_only=True)
    users = WorkspaceUserSerializer(many=True, read_only=True)
    channel_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Channel.objects.all(),
        write_only=True,
        required=False,
        source='channels'
    )
    user_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        source='users'
    )
    channels_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    shareable_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Workspace
        fields = [
            'id',
            'name',
            'picture',
            'slug',
            'is_active',
            'is_default',
            'shareable_url',
            'created_by',
            'channels',
            'channel_ids',
            'users',
            'user_ids',
            'channels_count',
            'users_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'shareable_url', 'created_by', 'created_at', 'updated_at']
    
    def get_channels_count(self, obj):
        """Get the count of channels in the workspace"""
        return obj.channels.count()
    
    def get_users_count(self, obj):
        """Get the count of users in the workspace"""
        return obj.users.count()
    
    def get_shareable_url(self, obj):
        """Generate the shareable URL for the workspace"""
        if obj.slug:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f'/api/v1/communication/workspaces/join/{obj.slug}/')
        return None


class WorkspaceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing workspaces"""
    created_by = CreatorSerializer(source='user', read_only=True)
    channels_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Workspace
        fields = ['id', 'name', 'picture', 'created_by', 'channels_count', 'users_count', 'is_active', 'is_default', 'created_at']
        read_only_fields = ['id', 'picture', 'created_by', 'is_default', 'created_at']
    
    def get_channels_count(self, obj):
        return obj.channels.count()
    
    def get_users_count(self, obj):
        return obj.users.count()


class AddRemoveChannelsSerializer(serializers.Serializer):
    """Serializer for adding/removing channels to/from workspaces"""
    channel_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text="List of channel IDs to add or remove"
    )
    
    def validate_channel_ids(self, value):
        """Validate that all channel IDs exist"""
        if not value:
            raise serializers.ValidationError("At least one channel ID is required")
        
        existing_channels = Channel.objects.filter(id__in=value).values_list('id', flat=True)
        missing_ids = set(value) - set(existing_channels)
        
        if missing_ids:
            raise serializers.ValidationError(
                f"Channels with IDs {list(missing_ids)} do not exist"
            )
        
        return value


# ====================
# Group Serializers
# ====================

class GroupUserSerializer(serializers.ModelSerializer):
    """Serializer for users in a group - minimal info"""
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'phone_number']
        read_only_fields = ['id', 'email', 'name', 'phone_number']


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Group model"""
    created_by = CreatorSerializer(source='user', read_only=True)
    admin = CreatorSerializer(source='group_admin', read_only=True)
    users = GroupUserSerializer(many=True, read_only=True)
    user_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        source='users'
    )
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = [
            'id',
            'name',
            'slug',
            'group_picture',
            'created_by',
            'admin',
            'users',
            'user_ids',
            'users_count',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_by', 'users_count', 'created_at', 'updated_at']
    
    def get_users_count(self, obj):
        """Get the count of users in the group"""
        return obj.users.count()


class GroupListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing groups"""
    created_by = CreatorSerializer(source='user', read_only=True)
    admin = CreatorSerializer(source='group_admin', read_only=True)
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'slug', 'created_by', 'admin', 'users_count', 'is_active', 'created_at']
        read_only_fields = ['id', 'slug', 'created_by', 'admin', 'users_count', 'created_at']
    
    def get_users_count(self, obj):
        return obj.users.count()


class GroupUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating group details (admin only)"""
    class Meta:
        model = Group
        fields = ['name', 'group_admin', 'group_picture', 'is_active']
    
    def validate_group_admin(self, value):
        """Ensure the new admin is a valid user"""
        if value and not isinstance(value, User):
            raise serializers.ValidationError("Invalid admin user")
        return value


# ====================
# Chat Serializers (REST history helpers)
# ====================

class ChatReactionSummarySerializer(serializers.Serializer):
    emoji = serializers.CharField()
    count = serializers.IntegerField()
    me = serializers.BooleanField()


class ChatMessageHistorySerializer(serializers.ModelSerializer):
    sender = CreatorSerializer(read_only=True)
    reply_to = serializers.SerializerMethodField()
    forwarded_from = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ['id', 'content', 'created_at', 'updated_at', 'sender', 'reply_to', 'forwarded_from', 'reactions', 'attachments']

    def _safe_text(self, value):
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        return str(value)

    def _profile_picture_url(self, user: User):
        if not user:
            return None
        picture = getattr(user, 'profile_picture', None)
        if not picture:
            return None
        request = self.context.get('request')
        url = picture.url
        return request.build_absolute_uri(url) if request else url

    def _mini_ref(self, msg: ChatMessage):
        return {
            'id': msg.id,
            'content': self._safe_text(msg.content),
            'sender': {
                'id': msg.sender_id,
                'name': getattr(msg.sender, 'name', None),
                'email': getattr(msg.sender, 'email', None),
                'profile_picture': self._profile_picture_url(msg.sender),
            },
            'created_at': msg.created_at,
        }

    def get_reply_to(self, obj: ChatMessage):
        if not obj.reply_to_id or not obj.reply_to:
            return None
        return self._mini_ref(obj.reply_to)

    def get_forwarded_from(self, obj: ChatMessage):
        if not obj.forwarded_from_id or not obj.forwarded_from:
            return None
        return self._mini_ref(obj.forwarded_from)

    def get_reactions(self, obj: ChatMessage):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        user_id = getattr(user, 'id', None)
        if not user_id:
            return []

        # Aggregate reactions by emoji.
        from django.db.models import Count
        qs = (
            ChatReaction.objects.filter(message=obj)
            .values('emoji')
            .annotate(count=Count('id'))
            .order_by('emoji')
        )
        mine = set(
            ChatReaction.objects.filter(message=obj, user_id=user_id).values_list('emoji', flat=True)
        )
        return [{'emoji': r['emoji'], 'count': r['count'], 'me': r['emoji'] in mine} for r in qs]

    def get_attachments(self, obj: ChatMessage):
        request = self.context.get('request')
        out = []
        for att in getattr(obj, 'attachments', []).all():
            url = att.file.url if att.file else None
            if url and request:
                url = request.build_absolute_uri(url)
            out.append(
                {
                    'id': att.id,
                    'kind': att.kind,
                    'url': url,
                    'original_name': self._safe_text(att.original_name),
                    'content_type': self._safe_text(att.content_type),
                    'size': att.size,
                    'created_at': att.created_at,
                }
            )
        return out


class ChatAttachmentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    kind = serializers.ChoiceField(
        choices=[c[0] for c in ChatAttachment.KIND_CHOICES],
        required=False,
        default=ChatAttachment.KIND_FILE,
    )


class ChatAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ChatAttachment
        fields = ['id', 'kind', 'url', 'original_name', 'content_type', 'size', 'created_at']

    def get_url(self, obj: ChatAttachment):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url
