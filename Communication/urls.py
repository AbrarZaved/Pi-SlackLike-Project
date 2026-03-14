from django.urls import path
from . import views

# Manually wire viewset actions into URL patterns (no DRF router)
channel_list = views.ChannelViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
channel_detail = views.ChannelViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})
channel_add_users = views.ChannelViewSet.as_view({'post': 'add_users'})
channel_remove_users = views.ChannelViewSet.as_view({'post': 'remove_users'})
channel_users = views.ChannelViewSet.as_view({'get': 'users'})
channel_leave = views.ChannelViewSet.as_view({'post': 'leave'})

workspace_list = views.WorkspaceViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
workspace_detail = views.WorkspaceViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})
workspace_add_users = views.WorkspaceViewSet.as_view({'post': 'add_users'})
workspace_remove_users = views.WorkspaceViewSet.as_view({'post': 'remove_users'})
workspace_add_channels = views.WorkspaceViewSet.as_view({'post': 'add_channels'})
workspace_remove_channels = views.WorkspaceViewSet.as_view({'post': 'remove_channels'})
workspace_users = views.WorkspaceViewSet.as_view({'get': 'users'})
workspace_channels = views.WorkspaceViewSet.as_view({'get': 'channels'})
workspace_join = views.WorkspaceViewSet.as_view({'get': 'join_workspace', 'post': 'join_workspace'})
workspace_join_channel = views.WorkspaceViewSet.as_view({'get': 'join_workspace_channel', 'post': 'join_workspace_channel'})

group_list = views.GroupViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
group_detail = views.GroupViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})
group_join = views.GroupViewSet.as_view({'post': 'join'})
group_leave = views.GroupViewSet.as_view({'post': 'leave'})
group_add_users = views.GroupViewSet.as_view({'post': 'add_users'})
group_remove_users = views.GroupViewSet.as_view({'post': 'remove_users'})
group_users = views.GroupViewSet.as_view({'get': 'users'})

urlpatterns = [
    # Channels
    path('channels/', channel_list, name='channel-list'),
    path('channels/<int:pk>/', channel_detail, name='channel-detail'),
    path('channels/<int:pk>/add_users/', channel_add_users, name='channel-add-users'),
    path('channels/<int:pk>/remove_users/', channel_remove_users, name='channel-remove-users'),
    path('channels/<int:pk>/users/', channel_users, name='channel-users'),
    path('channels/<int:pk>/leave/', channel_leave, name='channel-leave'),

    # Workspaces
    path('workspaces/', workspace_list, name='workspace-list'),
    path('workspaces/<int:pk>/', workspace_detail, name='workspace-detail'),
    path('workspaces/<int:pk>/add_users/', workspace_add_users, name='workspace-add-users'),
    path('workspaces/<int:pk>/remove_users/', workspace_remove_users, name='workspace-remove-users'),
    path('workspaces/<int:pk>/add_channels/', workspace_add_channels, name='workspace-add-channels'),
    path('workspaces/<int:pk>/remove_channels/', workspace_remove_channels, name='workspace-remove-channels'),
    path('workspaces/<int:pk>/users/', workspace_users, name='workspace-users'),
    path('workspaces/<int:pk>/channels/', workspace_channels, name='workspace-channels'),
    path('workspaces/join/<slug:slug>/', workspace_join, name='workspace-join'),
    path('workspaces/<slug:workspace_slug>/channels/join/<slug:channel_slug>/', workspace_join_channel, name='workspace-join-channel'),

    # Groups
    path('groups/', group_list, name='group-list'),
    path('groups/<int:pk>/', group_detail, name='group-detail'),
    path('groups/<int:pk>/join/', group_join, name='group-join'),
    path('groups/<int:pk>/leave/', group_leave, name='group-leave'),
    path('groups/<int:pk>/add_users/', group_add_users, name='group-add-users'),
    path('groups/<int:pk>/remove_users/', group_remove_users, name='group-remove-users'),
    path('groups/<int:pk>/users/', group_users, name='group-users'),
]
