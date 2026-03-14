"""
Serializers for Communication APIs
"""

from rest_framework import serializers
from .models import Channel, Workspace, Group
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
    class Meta:
        model = User
        fields = ['id', 'email', 'name']
        read_only_fields = ['id', 'email', 'name']


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
    users_count = serializers.SerializerMethodField()
    shareable_url = serializers.SerializerMethodField()
    workspaces_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Channel
        fields = [
            'id',
            'name',
            'type',
            'slug',
            'shareable_url',
            'workspaces_info',
            'created_by',
            'users',
            'user_ids',
            'users_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'shareable_url', 'workspaces_info', 'created_by', 'created_at', 'updated_at']
    
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


class ChannelListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing channels"""
    created_by = CreatorSerializer(source='user', read_only=True)
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Channel
        fields = ['id', 'name', 'type', 'created_by', 'users_count', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']
    
    def get_users_count(self, obj):
        return obj.users.count()


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
        fields = ['id', 'name', 'picture', 'created_by', 'channels_count', 'users_count', 'created_at']
        read_only_fields = ['id', 'picture', 'created_by', 'created_at']
    
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
