from django.urls import re_path

from . import consumers


websocket_urlpatterns = [
    # Channel chat
    re_path(r'^ws/chat/channels/(?P<channel_id>\d+)/$', consumers.ChannelChatConsumer.as_asgi()),

    # Group chat
    re_path(r'^ws/chat/groups/(?P<group_id>\d+)/$', consumers.GroupChatConsumer.as_asgi()),

    # 1:1 direct messages (connect with the other user's id; thread auto-created)
    re_path(r'^ws/chat/dm/(?P<other_user_id>\d+)/$', consumers.DirectMessageConsumer.as_asgi()),

    # Search people (for chat list)
    re_path(r'^ws/chat/search/$', consumers.ChatSearchConsumer.as_asgi()),
]
