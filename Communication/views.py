from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Channel, Workspace, Group, ChatMessage, DirectMessageThread
from .serializers import (
    ChannelSerializer,
    ChannelListSerializer,
    WorkspaceSerializer,
    WorkspaceListSerializer,
    AddRemoveUsersSerializer,
    AddRemoveChannelsSerializer,
    GroupSerializer,
    GroupListSerializer,
    GroupUpdateSerializer,
    ChatMessageHistorySerializer
)
from authentication.models import User


# ====================
# Channel ViewSet
# ====================

class ChannelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing channels.
    
    Provides CRUD operations for channels and user management.
    """
    queryset = Channel.objects.all().prefetch_related('users')
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use lightweight serializer for list action"""
        if self.action == 'list':
            return ChannelListSerializer
        return ChannelSerializer
    
    @extend_schema(
        description="Get all channels",
        parameters=[
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                description='Filter by channel type (public/private)',
                required=False
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                description='Search channels by name',
                required=False
            ),
            OpenApiParameter(
                name='workspace_id',
                type=OpenApiTypes.INT,
                description='Filter channels by workspace ID',
                required=False
            )
        ],
        tags=['Channels']
    )
    def list(self, request):
        """List all channels with optional filters"""
        queryset = self.get_queryset()
        
        # Filter by workspace
        workspace_id = request.query_params.get('workspace_id', None)
        workspace = None
        if workspace_id:
            queryset = queryset.filter(workspaces__id=workspace_id)
            try:
                workspace = Workspace.objects.get(id=workspace_id)
            except Workspace.DoesNotExist:
                pass
        
        # Filter by type
        channel_type = request.query_params.get('type', None)
        if channel_type:
            queryset = queryset.filter(type=channel_type)
        
        # Search by name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        serializer = self.get_serializer(
            queryset, 
            many=True, 
            context={'request': request, 'workspace': workspace}
        )
        return Response(serializer.data)
    
    @extend_schema(
        description="Create a new channel",
        request=ChannelSerializer,
        responses={201: ChannelSerializer},
        tags=['Channels']
    )
    def create(self, request):
        """Create a new channel"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        description="Get channel details",
        responses={200: ChannelSerializer},
        parameters=[
            OpenApiParameter(
                name='workspace_id',
                type=OpenApiTypes.INT,
                description='Workspace ID for context (affects shareable_url)',
                required=False
            )
        ],
        tags=['Channels']
    )
    def retrieve(self, request, pk=None):
        """Get a specific channel"""
        channel = self.get_object()
        
        # Get workspace context if provided
        workspace = None
        workspace_id = request.query_params.get('workspace_id', None)
        if workspace_id:
            try:
                workspace = Workspace.objects.get(id=workspace_id)
                # Verify channel belongs to this workspace
                if channel not in workspace.channels.all():
                    workspace = None
            except Workspace.DoesNotExist:
                pass
        
        serializer = self.get_serializer(channel, context={'request': request, 'workspace': workspace})
        return Response(serializer.data)
    
    @extend_schema(
        description="Update channel details",
        request=ChannelSerializer,
        responses={200: ChannelSerializer},
        tags=['Channels']
    )
    def update(self, request, pk=None):
        """Update a channel"""
        channel = self.get_object()
        serializer = self.get_serializer(channel, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @extend_schema(
        description="Partially update channel details",
        request=ChannelSerializer,
        responses={200: ChannelSerializer},
        tags=['Channels']
    )
    def partial_update(self, request, pk=None):
        """Partially update a channel"""
        channel = self.get_object()
        serializer = self.get_serializer(channel, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @extend_schema(
        description="Delete a channel",
        responses={204: None},
        tags=['Channels']

    )
    def destroy(self, request, pk=None):
        """Delete a channel"""
        channel = self.get_object()
        channel.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @extend_schema(
        description="Add users to a channel",
        request=AddRemoveUsersSerializer,
        responses={200: ChannelSerializer},
        tags=['Channels']
    )
    @action(detail=True, methods=['post'])
    def add_users(self, request, pk=None):
        """Add users to a channel"""
        channel = self.get_object()
        serializer = AddRemoveUsersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        users = User.objects.filter(id__in=user_ids)
        channel.users.add(*users)
        
        response_serializer = ChannelSerializer(channel)
        return Response({
            'message': f'Successfully added {len(users)} user(s) to the channel',
            'channel': response_serializer.data
        })
    
    @extend_schema(
        description="Remove users from a channel",
        request=AddRemoveUsersSerializer,
        responses={200: ChannelSerializer},
        tags=['Channels']
    )
    @action(detail=True, methods=['post'])
    def remove_users(self, request, pk=None):
        """Remove users from a channel"""
        channel = self.get_object()
        serializer = AddRemoveUsersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        users = User.objects.filter(id__in=user_ids)
        channel.users.remove(*users)
        
        response_serializer = ChannelSerializer(channel)
        return Response({
            'message': f'Successfully removed {len(users)} user(s) from the channel',
            'channel': response_serializer.data
        })
    
    @extend_schema(
        description="Leave the channel (remove yourself)",
        responses={200: ChannelSerializer},
        tags=['Channels']
    )
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Remove the authenticated user from the channel"""
        channel = self.get_object()
        if request.user in channel.users.all():
            channel.users.remove(request.user)
            message = 'Successfully left the channel'
        else:
            message = 'You are not a member of this channel'

        response_serializer = ChannelSerializer(channel)
        return Response({
            'message': message,
            'channel': response_serializer.data
        })

    @extend_schema(
        description="Get all users in a channel",
        responses={200: ChannelSerializer},
        tags=['Channels']
    )
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in a channel"""
        channel = self.get_object()
        users = channel.users.all()
        from .serializers import ChannelUserSerializer
        serializer = ChannelUserSerializer(users, many=True)
        return Response(serializer.data)


# ====================
# Workspace ViewSet
# ====================

class WorkspaceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing workspaces.
    
    Provides CRUD operations for workspaces, user management, and channel management.
    """
    queryset = Workspace.objects.all().prefetch_related('users', 'channels')
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use lightweight serializer for list action"""
        if self.action == 'list':
            return WorkspaceListSerializer
        return WorkspaceSerializer
    
    @extend_schema(
        description="Get all workspaces",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                description='Search workspaces by name',
                required=False
            )
        ],
        tags=['Workspaces']
    )
    def list(self, request):
        """List all workspaces with optional filters"""
        queryset = self.get_queryset()
        
        # Search by name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Create a new workspace",
        request=WorkspaceSerializer,
        responses={201: WorkspaceSerializer},
        tags=['Workspaces']
    )
    def create(self, request):
        """Create a new workspace"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        description="Get workspace details",
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    def retrieve(self, request, pk=None):
        """Get a specific workspace"""
        workspace = self.get_object()
        serializer = self.get_serializer(workspace)
        return Response(serializer.data)
    
    @extend_schema(
        description="Update workspace details",
        request=WorkspaceSerializer,
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    def update(self, request, pk=None):
        """Update a workspace"""
        workspace = self.get_object()
        serializer = self.get_serializer(workspace, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @extend_schema(
        description="Partially update workspace details",
        request=WorkspaceSerializer,
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    def partial_update(self, request, pk=None):
        """Partially update a workspace"""
        workspace = self.get_object()
        serializer = self.get_serializer(workspace, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @extend_schema(
        description="Delete a workspace",
        responses={204: None},
        tags=['Workspaces']
    )
    def destroy(self, request, pk=None):
        """Delete a workspace"""
        workspace = self.get_object()
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @extend_schema(
        description="Add users to a workspace",
        request=AddRemoveUsersSerializer,
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    @action(detail=True, methods=['post'])
    def add_users(self, request, pk=None):
        """Add users to a workspace"""
        workspace = self.get_object()
        serializer = AddRemoveUsersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        users = User.objects.filter(id__in=user_ids)
        workspace.users.add(*users)
        
        response_serializer = WorkspaceSerializer(workspace)
        return Response({
            'message': f'Successfully added {len(users)} user(s) to the workspace',
            'workspace': response_serializer.data
        })
    
    @extend_schema(
        description="Remove users from a workspace",
        request=AddRemoveUsersSerializer,
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    @action(detail=True, methods=['post'])
    def remove_users(self, request, pk=None):
        """Remove users from a workspace"""
        workspace = self.get_object()
        serializer = AddRemoveUsersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        users = User.objects.filter(id__in=user_ids)
        workspace.users.remove(*users)
        
        response_serializer = WorkspaceSerializer(workspace)
        return Response({
            'message': f'Successfully removed {len(users)} user(s) from the workspace',
            'workspace': response_serializer.data
        })
    
    @extend_schema(
        description="Add channels to a workspace",
        request=AddRemoveChannelsSerializer,
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    @action(detail=True, methods=['post'])
    def add_channels(self, request, pk=None):
        """Add channels to a workspace"""
        workspace = self.get_object()
        serializer = AddRemoveChannelsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        channel_ids = serializer.validated_data['channel_ids']
        channels = Channel.objects.filter(id__in=channel_ids)
        workspace.channels.add(*channels)
        
        response_serializer = WorkspaceSerializer(workspace)
        return Response({
            'message': f'Successfully added {len(channels)} channel(s) to the workspace',
            'workspace': response_serializer.data
        })
    
    @extend_schema(
        description="Remove channels from a workspace",
        request=AddRemoveChannelsSerializer,
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    @action(detail=True, methods=['post'])
    def remove_channels(self, request, pk=None):
        """Remove channels from a workspace"""
        workspace = self.get_object()
        serializer = AddRemoveChannelsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        channel_ids = serializer.validated_data['channel_ids']
        channels = Channel.objects.filter(id__in=channel_ids)
        workspace.channels.remove(*channels)
        
        response_serializer = WorkspaceSerializer(workspace)
        return Response({
            'message': f'Successfully removed {len(channels)} channel(s) from the workspace',
            'workspace': response_serializer.data
        })
    
    @extend_schema(
        description="Get all users in a workspace",
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in a workspace"""
        workspace = self.get_object()
        users = workspace.users.all()
        from .serializers import WorkspaceUserSerializer
        serializer = WorkspaceUserSerializer(users, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get all channels in a workspace",
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    @action(detail=True, methods=['get'])
    def channels(self, request, pk=None):
        """Get all channels in a workspace"""
        workspace = self.get_object()
        channels = workspace.channels.all()
        from .serializers import WorkspaceChannelSerializer
        serializer = WorkspaceChannelSerializer(channels, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Join a workspace via shareable slug",
        responses={200: WorkspaceSerializer},
        tags=['Workspaces']
    )
    @action(detail=False, methods=['get', 'post'], url_path='join/(?P<slug>[^/.]+)')
    def join_workspace(self, request, slug=None):
        """Join a workspace using its shareable slug"""
        try:
            workspace = Workspace.objects.get(slug=slug)
        except Workspace.DoesNotExist:
            return Response(
                {'error': 'Workspace not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Add the authenticated user to the workspace
        if request.user not in workspace.users.all():
            workspace.users.add(request.user)
            message = f'Successfully joined workspace: {workspace.name}'
        else:
            message = f'You are already a member of workspace: {workspace.name}'
        
        serializer = WorkspaceSerializer(workspace, context={'request': request})
        return Response({
            'message': message,
            'workspace': serializer.data
        })
    
    @extend_schema(
        description="Join a channel within a workspace via shareable slugs",
        responses={200: ChannelSerializer},
        tags=['Workspaces']
    )
    @action(
        detail=False, 
        methods=['get', 'post'], 
        url_path='(?P<workspace_slug>[^/.]+)/channels/join/(?P<channel_slug>[^/.]+)'
    )
    def join_workspace_channel(self, request, workspace_slug=None, channel_slug=None):
        """Join a channel within a specific workspace using shareable slugs"""
        # Find the workspace
        try:
            workspace = Workspace.objects.get(slug=workspace_slug)
        except Workspace.DoesNotExist:
            return Response(
                {'error': 'Workspace not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Find the channel
        try:
            channel = Channel.objects.get(slug=channel_slug)
        except Channel.DoesNotExist:
            return Response(
                {'error': 'Channel not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify the channel belongs to this workspace
        if channel not in workspace.channels.all():
            return Response(
                {'error': 'This channel does not belong to the specified workspace'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add the authenticated user to both workspace and channel
        messages = []
        
        if request.user not in workspace.users.all():
            workspace.users.add(request.user)
            messages.append(f'Added to workspace: {workspace.name}')
        
        if request.user not in channel.users.all():
            channel.users.add(request.user)
            messages.append(f'Joined channel: {channel.name}')
        
        if not messages:
            messages.append(f'You are already a member of this channel in {workspace.name}')
        
        from .serializers import ChannelSerializer
        serializer = ChannelSerializer(channel, context={'request': request, 'workspace': workspace})
        return Response({
            'message': ' | '.join(messages),
            'channel': serializer.data,
            'workspace': {
                'id': workspace.id,
                'name': workspace.name,
                'slug': workspace.slug
            }
        })


# ====================
# Group ViewSet
# ====================

class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing groups.
    
    Provides CRUD operations for groups, user management, and admin utilities.
    """
    queryset = Group.objects.all().prefetch_related('users')
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use appropriate serializer based on action"""
        if self.action == 'list':
            return GroupListSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return GroupUpdateSerializer
        return GroupSerializer
    
    @extend_schema(
        description="Get all groups",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                description='Search groups by name',
                required=False
            )
        ],
        tags=['Groups']
    )
    def list(self, request):
        """List all groups with optional filters"""
        queryset = self.get_queryset()
        
        # Search by name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Create a new group",
        request=GroupSerializer,
        responses={201: GroupSerializer},
        tags=['Groups']
    )
    def create(self, request):
        """Create a new group"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, group_admin=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        description="Get group details",
        responses={200: GroupSerializer},
        tags=['Groups']
    )
    def retrieve(self, request, pk=None):
        """Get a specific group"""
        group = self.get_object()
        serializer = self.get_serializer(group)
        return Response(serializer.data)
    
    @extend_schema(
        description="Update group details (admin only)",
        request=GroupUpdateSerializer,
        responses={200: GroupUpdateSerializer},
        tags=['Groups']
    )
    def update(self, request, pk=None):
        """Update a group (admin/owner only)"""
        group = self.get_object()
        
        # Check if user is admin or group owner
        if request.user != group.group_admin and request.user != group.user:
            return Response(
                {'error': 'Only group admin or owner can update this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(group, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @extend_schema(
        description="Partially update group details (admin only)",
        request=GroupUpdateSerializer,
        responses={200: GroupUpdateSerializer},
        tags=['Groups']
    )
    def partial_update(self, request, pk=None):
        """Partially update a group (admin/owner only)"""
        group = self.get_object()
        
        # Check if user is admin or group owner
        if request.user != group.group_admin and request.user != group.user:
            return Response(
                {'error': 'Only group admin or owner can update this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @extend_schema(
        description="Delete a group (admin only)",
        responses={204: None},
        tags=['Groups']
    )
    def destroy(self, request, pk=None):
        """Delete a group (admin/owner only)"""
        group = self.get_object()
        
        # Check if user is admin or group owner
        if request.user != group.group_admin and request.user != group.user:
            return Response(
                {'error': 'Only group admin or owner can delete this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @extend_schema(
        description="Join a group",
        responses={200: GroupSerializer},
        tags=['Groups']
    )
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join a group"""
        group = self.get_object()
        
        if request.user in group.users.all():
            return Response(
                {'message': 'You are already a member of this group', 'group': GroupSerializer(group).data},
                status=status.HTTP_200_OK
            )
        
        group.users.add(request.user)
        serializer = self.get_serializer(group)
        return Response({
            'message': f'Successfully joined group: {group.name}',
            'group': serializer.data
        })
    
    @extend_schema(
        description="Leave a group",
        responses={200: GroupSerializer},
        tags=['Groups']
    )
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave a group"""
        group = self.get_object()
        
        if request.user not in group.users.all():
            return Response(
                {'message': 'You are not a member of this group', 'group': GroupSerializer(group).data},
                status=status.HTTP_200_OK
            )
        
        group.users.remove(request.user)
        serializer = self.get_serializer(group)
        return Response({
            'message': f'Successfully left group: {group.name}',
            'group': serializer.data
        })
    
    @extend_schema(
        description="Add users to a group (admin only)",
        request=AddRemoveUsersSerializer,
        responses={200: GroupSerializer},
        tags=['Groups']
    )
    @action(detail=True, methods=['post'])
    def add_users(self, request, pk=None):
        """Add users to a group (admin/owner only)"""
        group = self.get_object()
        
        # Check if user is admin or group owner
        if request.user != group.group_admin and request.user != group.user:
            return Response(
                {'error': 'Only group admin or owner can add users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AddRemoveUsersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        users = User.objects.filter(id__in=user_ids)
        group.users.add(*users)
        
        response_serializer = self.get_serializer(group)
        return Response({
            'message': f'Successfully added {len(users)} user(s) to the group',
            'group': response_serializer.data
        })
    
    @extend_schema(
        description="Remove users from a group (admin only)",
        request=AddRemoveUsersSerializer,
        responses={200: GroupSerializer},
        tags=['Groups']
    )
    @action(detail=True, methods=['post'])
    def remove_users(self, request, pk=None):
        """Remove users from a group (admin/owner only)"""
        group = self.get_object()
        
        # Check if user is admin or group owner
        if request.user != group.group_admin and request.user != group.user:
            return Response(
                {'error': 'Only group admin or owner can remove users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AddRemoveUsersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        users = User.objects.filter(id__in=user_ids)
        group.users.remove(*users)
        
        response_serializer = self.get_serializer(group)
        return Response({
            'message': f'Successfully removed {len(users)} user(s) from the group',
            'group': response_serializer.data
        })
    
    @extend_schema(
        description="Get all users in a group",
        responses={200: GroupSerializer},
        tags=['Groups']
    )
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in a group"""
        group = self.get_object()
        users = group.users.all()
        from .serializers import GroupUserSerializer
        serializer = GroupUserSerializer(users, many=True)
        return Response(serializer.data)


# ====================
# Chat REST helpers
# ====================

class ChatViewSet(viewsets.ViewSet):
    """REST endpoints for chat history and websocket endpoint discovery."""

    permission_classes = [IsAuthenticated]

    def _parse_limit(self, request, default=50, max_limit=200):
        try:
            limit = int(request.query_params.get('limit', default))
        except (TypeError, ValueError):
            limit = default
        return max(1, min(limit, max_limit))

    def _parse_before_id(self, request):
        before_id = request.query_params.get('before_id')
        try:
            return int(before_id) if before_id else None
        except (TypeError, ValueError):
            return None

    @extend_schema(
        description="Return websocket URL patterns for chat.",
        tags=['Chat']
    )
    def ws_endpoints(self, request):
        return Response({
            'channels': '/ws/chat/channels/<channel_id>/?token=<JWT>',
            'groups': '/ws/chat/groups/<group_id>/?token=<JWT>',
            'dm': '/ws/chat/dm/<other_user_id>/?token=<JWT>',
            'search': '/ws/chat/search/?token=<JWT>',
        })

    @extend_schema(
        description="Get message history for a channel (requires membership).",
        tags=['Chat']
    )
    def channel_messages(self, request, channel_id: int):
        if not Channel.objects.filter(id=channel_id, users=request.user).exists():
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        limit = self._parse_limit(request)
        before_id = self._parse_before_id(request)

        qs = ChatMessage.objects.filter(channel_id=channel_id).select_related(
            'sender', 'reply_to__sender', 'forwarded_from__sender'
        )
        if before_id:
            qs = qs.filter(id__lt=before_id)

        items = list(qs.order_by('-created_at')[:limit])
        items.reverse()
        serializer = ChatMessageHistorySerializer(items, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        description="Get message history for a group (requires membership).",
        tags=['Chat']
    )
    def group_messages(self, request, group_id: int):
        if not Group.objects.filter(id=group_id, users=request.user).exists():
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        limit = self._parse_limit(request)
        before_id = self._parse_before_id(request)

        qs = ChatMessage.objects.filter(group_id=group_id).select_related(
            'sender', 'reply_to__sender', 'forwarded_from__sender'
        )
        if before_id:
            qs = qs.filter(id__lt=before_id)

        items = list(qs.order_by('-created_at')[:limit])
        items.reverse()
        serializer = ChatMessageHistorySerializer(items, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        description="Get message history for a 1:1 DM with another user (auto-creates thread).",
        tags=['Chat']
    )
    def dm_messages(self, request, other_user_id: int):
        if request.user.id == other_user_id:
            return Response({'error': 'Invalid user'}, status=status.HTTP_400_BAD_REQUEST)

        other = User.objects.filter(id=other_user_id, is_active=True).first()
        if not other:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        thread = DirectMessageThread.get_or_create_for_users(request.user, other)

        limit = self._parse_limit(request)
        before_id = self._parse_before_id(request)

        qs = ChatMessage.objects.filter(dm_thread=thread).select_related(
            'sender', 'reply_to__sender', 'forwarded_from__sender'
        )
        if before_id:
            qs = qs.filter(id__lt=before_id)

        items = list(qs.order_by('-created_at')[:limit])
        items.reverse()
        serializer = ChatMessageHistorySerializer(items, many=True, context={'request': request})
        return Response({'thread_id': thread.id, 'messages': serializer.data})

