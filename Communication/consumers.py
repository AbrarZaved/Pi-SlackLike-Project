from __future__ import annotations

from typing import Any, Dict, Optional, List

from collections import defaultdict
import re

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.db import transaction
from django.db.models import Count, Q
from django.utils.text import Truncator

from authentication.models import User
from .models import Channel, Group, DirectMessageThread, ChatMessage, ChatReaction, ChatAttachment


HISTORY_LIMIT = 50

# In-process presence tracking per chat room.
# Key: room_group_name, Value: {user_id: connection_count}
_ACTIVE_ROOM_USERS: Dict[str, Dict[int, int]] = defaultdict(dict)


def _presence_inc(room_group_name: str, user_id: int) -> None:
    counts = _ACTIVE_ROOM_USERS.get(room_group_name)
    if counts is None:
        counts = {}
        _ACTIVE_ROOM_USERS[room_group_name] = counts
    counts[user_id] = int(counts.get(user_id, 0)) + 1


def _presence_dec(room_group_name: str, user_id: int) -> None:
    counts = _ACTIVE_ROOM_USERS.get(room_group_name)
    if not counts:
        return
    new_val = int(counts.get(user_id, 0)) - 1
    if new_val > 0:
        counts[user_id] = new_val
    else:
        counts.pop(user_id, None)
        if not counts:
            _ACTIVE_ROOM_USERS.pop(room_group_name, None)


def _is_user_connected(room_group_name: str, user_id: int) -> bool:
    counts = _ACTIVE_ROOM_USERS.get(room_group_name)
    return bool(counts and int(counts.get(user_id, 0)) > 0)


_MENTION_EMAIL_RE = re.compile(r'@([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')


_MENTION_NAME_RE = re.compile(r'@([A-Za-z0-9_.\-](?:[A-Za-z0-9_.\- ]{0,62}[A-Za-z0-9_.\-])?)')


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ''
    return ''.join(ch for ch in value.strip().lower() if not ch.isspace())


def _extract_mentioned_names(content: str) -> List[str]:
    """Extract @name mentions.

    Mention format: @name (spaces allowed inside, no leading/trailing spaces).
    Matching uses User.name after normalization
    (lowercase, spaces removed).
    """
    if not content:
        return []
    names = [_normalize_name(m.group(1)) for m in _MENTION_NAME_RE.finditer(content)]
    # De-duplicate while preserving order
    seen = set()
    out: List[str] = []
    for n in names:
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


class BaseChatConsumer(AsyncJsonWebsocketConsumer):
    """Shared behavior for chat consumers."""

    room_group_name: str

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        ok = await self._authorize_and_set_room()
        if not ok:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Mark presence for this chat room so we can suppress notifications
        # when the user is already connected.
        _presence_inc(self.room_group_name, int(user.id))
        await self.accept()

        history = await self._get_history()
        await self.send_json({'type': 'history', 'items': history})

    async def disconnect(self, close_code):
        if getattr(self, 'room_group_name', None):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

            user = self.scope.get('user')
            if user and getattr(user, 'is_authenticated', False):
                _presence_dec(self.room_group_name, int(user.id))

    async def receive_json(self, content: Dict[str, Any], **kwargs):
        message_type = content.get('type')
        if message_type == 'message.send':
            await self._handle_message_send(content)
        elif message_type == 'reaction.add':
            await self._handle_reaction_add(content)
        elif message_type == 'reaction.remove':
            await self._handle_reaction_remove(content)
        else:
            await self.send_json({'type': 'error', 'message': 'Unknown event type'})

    def _parse_optional_int(self, value: Any, field_name: str) -> Optional[int]:
        if value is None or value == '':
            return None
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            value = value.strip()
            if value.isdigit():
                return int(value)
        raise ValueError(f"{field_name} must be an integer")

    def _parse_required_int(self, value: Any, field_name: str) -> int:
        parsed = self._parse_optional_int(value, field_name)
        if parsed is None:
            raise ValueError(f"{field_name} is required")
        return parsed

    def _parse_int_list(self, value: Any, field_name: str, *, max_items: int = 10) -> List[int]:
        if value is None or value == '':
            return []
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list")
        if len(value) > max_items:
            raise ValueError(f"{field_name} can include at most {max_items} items")

        out: List[int] = []
        for raw in value:
            out.append(self._parse_required_int(raw, field_name))

        # De-dupe while preserving order
        seen = set()
        uniq: List[int] = []
        for i in out:
            if i in seen:
                continue
            seen.add(i)
            uniq.append(i)
        return uniq

    async def chat_event(self, event: Dict[str, Any]):
        await self.send_json(event['payload'])

    async def _broadcast(self, payload: Dict[str, Any]):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat.event',
                'payload': payload,
            },
        )

    # ----- abstract-ish hooks -----

    async def _authorize_and_set_room(self) -> bool:
        raise NotImplementedError

    async def _get_target_kwargs(self) -> Dict[str, Any]:
        """Returns kwargs to attach message to the correct target."""
        raise NotImplementedError

    async def _is_same_target(self, message: ChatMessage) -> bool:
        """True if the given message belongs to this consumer's target."""
        raise NotImplementedError

    # ----- handlers -----

    async def _handle_message_send(self, data: Dict[str, Any]):
        content = (data.get('content') or '').strip()
        try:
            reply_to_id = self._parse_optional_int(data.get('reply_to'), 'reply_to')
            forward_from_id = self._parse_optional_int(data.get('forward_from'), 'forward_from')
            attachment_ids = self._parse_int_list(data.get('attachment_ids'), 'attachment_ids')
        except ValueError as e:
            await self.send_json({'type': 'error', 'message': str(e)})
            return

        if not content and not forward_from_id and not attachment_ids:
            await self.send_json({'type': 'error', 'message': 'content is required unless forwarding or attaching media'})
            return

        user: User = self.scope['user']

        try:
            msg = await self._create_message(
            sender_id=user.id,
            content=content,
            reply_to_id=reply_to_id,
            forward_from_id=forward_from_id,
            attachment_ids=attachment_ids,
        )
        except ValueError as e:
            await self.send_json({'type': 'error', 'message': str(e)})
            return

        payload = {'type': 'message.new', 'message': msg}
        await self._broadcast(payload)

        # In-app notifications (delivered via websocket) for other participants.
        try:
            await self._create_notifications_for_message(message_id=int(msg['id']))
        except Exception:
            # Never break chat flow due to notifications
            pass

        # Automations: auto replies / actions for channel messages
        try:
            target_kwargs = await self._get_target_kwargs()
            if target_kwargs.get('channel_id'):
                auto_messages = await self._run_channel_message_automations(original_message_id=int(msg['id']))
                for auto_msg in auto_messages:
                    await self._broadcast({'type': 'message.new', 'message': auto_msg})
        except Exception:
            # Never break chat flow due to automations
            pass

    @database_sync_to_async
    def _run_channel_message_automations(self, *, original_message_id: int) -> List[Dict[str, Any]]:
        from Admin.automation_engine import run_new_channel_message

        original = (
            ChatMessage.objects.filter(id=original_message_id)
            .select_related('sender', 'channel', 'group', 'dm_thread')
            .first()
        )
        if not original or not original.channel_id:
            return []

        created = run_new_channel_message(message=original)
        if not created:
            return []

        reply_ids = [m.id for m in created]
        replies = (
            ChatMessage.objects.filter(id__in=reply_ids)
            .select_related('sender', 'reply_to__sender', 'forwarded_from__sender')
            .prefetch_related('reactions')
            .order_by('created_at')
        )

        return [self._serialize_message(m) for m in replies]

    @database_sync_to_async
    def _create_notifications_for_message(self, *, message_id: int) -> None:
        from Notification.services import create_notification_for_user

        message = (
            ChatMessage.objects.filter(id=message_id)
            .select_related('sender', 'channel', 'group', 'dm_thread')
            .first()
        )
        if not message:
            return

        sender_id = message.sender_id
        preview = Truncator(message.content or '').chars(120)
        mentioned_names = set(_extract_mentioned_names(message.content or ''))

        if message.channel_id and message.channel:
            channel = message.channel
            recipients = channel.users.exclude(id=sender_id)
            for user in recipients:
                # Suppress notifications for users already connected to this channel chat websocket.
                if _is_user_connected(f'chat_channel_{channel.id}', int(user.id)):
                    continue

                is_mention = bool(_normalize_name(getattr(user, 'name', None)) in mentioned_names)
                create_notification_for_user(
                    user=user,
                    notification_type='chat.mention' if is_mention else 'chat.channel_message',
                    title='New message',
                    body=preview,
                    data={
                        'channel_id': channel.id,
                        'channel_name': channel.name,
                        'message_id': message.id,
                        'sender_id': sender_id,
                        'is_mention': is_mention,
                    },
                )
            return

        if message.group_id and message.group:
            group = message.group
            recipients = group.users.exclude(id=sender_id)
            for user in recipients:
                if _is_user_connected(f'chat_group_{group.id}', int(user.id)):
                    continue

                is_mention = bool(_normalize_name(getattr(user, 'name', None)) in mentioned_names)
                create_notification_for_user(
                    user=user,
                    notification_type='chat.mention' if is_mention else 'chat.group_message',
                    title='New message',
                    body=preview,
                    data={
                        'group_id': group.id,
                        'group_name': group.name,
                        'message_id': message.id,
                        'sender_id': sender_id,
                        'is_mention': is_mention,
                    },
                )
            return

        if message.dm_thread_id and message.dm_thread:
            thread = message.dm_thread
            other_user_id = thread.user_a_id if sender_id != thread.user_a_id else thread.user_b_id
            other = User.objects.filter(id=other_user_id, is_active=True).first()
            if not other:
                return

            if _is_user_connected(f'chat_dm_{thread.id}', int(other.id)):
                return

            create_notification_for_user(
                user=other,
                notification_type='chat.direct_message',
                title='New message',
                body=preview,
                data={'dm_thread_id': thread.id, 'message_id': message.id, 'sender_id': sender_id},
            )

    async def _handle_reaction_add(self, data: Dict[str, Any]):
        message_id = data.get('message_id')
        emoji = data.get('emoji')
        if not emoji:
            await self.send_json({'type': 'error', 'message': 'emoji is required'})
            return

        try:
            message_id_int = self._parse_required_int(message_id, 'message_id')
        except ValueError as e:
            await self.send_json({'type': 'error', 'message': str(e)})
            return

        user: User = self.scope['user']
        result = await self._add_reaction(message_id=message_id_int, user_id=user.id, emoji=str(emoji))
        if not result:
            await self.send_json({'type': 'error', 'message': 'Invalid message or not allowed'})
            return

        payload = {'type': 'reaction.updated', 'message_id': message_id_int, 'reactions': result}
        await self._broadcast(payload)

    async def _handle_reaction_remove(self, data: Dict[str, Any]):
        message_id = data.get('message_id')
        emoji = data.get('emoji')
        if not emoji:
            await self.send_json({'type': 'error', 'message': 'emoji is required'})
            return

        try:
            message_id_int = self._parse_required_int(message_id, 'message_id')
        except ValueError as e:
            await self.send_json({'type': 'error', 'message': str(e)})
            return

        user: User = self.scope['user']
        result = await self._remove_reaction(message_id=message_id_int, user_id=user.id, emoji=str(emoji))
        if result is None:
            await self.send_json({'type': 'error', 'message': 'Invalid message or not allowed'})
            return

        payload = {'type': 'reaction.updated', 'message_id': message_id_int, 'reactions': result}
        await self._broadcast(payload)

    # ----- DB operations -----

    async def _get_history(self) -> List[Dict[str, Any]]:
        return await self._db_get_history()

    @database_sync_to_async
    def _db_get_history(self) -> List[Dict[str, Any]]:
        target_kwargs = self._sync_get_target_kwargs()
        qs = (
            ChatMessage.objects.filter(**target_kwargs)
            .select_related('sender', 'reply_to__sender', 'forwarded_from__sender')
            .prefetch_related('reactions', 'attachments')
            .order_by('-created_at')[:HISTORY_LIMIT]
        )

        items = [self._serialize_message(m) for m in reversed(list(qs))]
        return items

    def _sync_get_target_kwargs(self) -> Dict[str, Any]:
        # Sync wrapper for _get_target_kwargs so we can use it in sync DB functions.
        raise NotImplementedError

    @database_sync_to_async
    def _create_message(
        self,
        *,
        sender_id: int,
        content: str,
        reply_to_id: Optional[int],
        forward_from_id: Optional[int],
        attachment_ids: List[int],
    ) -> Dict[str, Any]:
        target_kwargs = self._sync_get_target_kwargs()

        reply_to = None
        if reply_to_id:
            candidate = ChatMessage.objects.filter(id=reply_to_id).select_related('sender').first()
            if candidate and self._sync_is_same_target(candidate):
                reply_to = candidate

        forwarded_from = None
        if forward_from_id:
            candidate = ChatMessage.objects.filter(id=forward_from_id).select_related('sender').first()
            if candidate and self._sync_is_same_target(candidate):
                forwarded_from = candidate

        with transaction.atomic():
            msg = ChatMessage.objects.create(
                sender_id=sender_id,
                content=content,
                reply_to=reply_to,
                forwarded_from=forwarded_from,
                **target_kwargs,
            )

            if attachment_ids:
                locked = list(
                    ChatAttachment.objects.select_for_update()
                    .filter(
                        id__in=attachment_ids,
                        uploaded_by_id=sender_id,
                        message__isnull=True,
                    )
                )
                if len(locked) != len(attachment_ids):
                    raise ValueError('Invalid attachment_ids (not found, not yours, or already used)')
                ChatAttachment.objects.filter(id__in=[a.id for a in locked]).update(message=msg)

        msg = (
            ChatMessage.objects.filter(id=msg.id)
            .select_related('sender', 'reply_to__sender', 'forwarded_from__sender')
            .prefetch_related('reactions', 'attachments')
            .get()
        )

        return self._serialize_message(msg)

    @database_sync_to_async
    def _add_reaction(self, *, message_id: int, user_id: int, emoji: str) -> Optional[List[Dict[str, Any]]]:
        msg = ChatMessage.objects.filter(id=message_id).first()
        if not msg or not self._sync_is_same_target(msg):
            return None

        ChatReaction.objects.get_or_create(message_id=message_id, user_id=user_id, emoji=emoji)
        return self._serialize_reactions(message_id, user_id)

    @database_sync_to_async
    def _remove_reaction(self, *, message_id: int, user_id: int, emoji: str) -> Optional[List[Dict[str, Any]]]:
        msg = ChatMessage.objects.filter(id=message_id).first()
        if not msg or not self._sync_is_same_target(msg):
            return None

        ChatReaction.objects.filter(message_id=message_id, user_id=user_id, emoji=emoji).delete()
        return self._serialize_reactions(message_id, user_id)

    def _serialize_message(self, msg: ChatMessage) -> Dict[str, Any]:
        sender = msg.sender
        reply_to = None
        if msg.reply_to_id and msg.reply_to:
            reply_to = {
                'id': msg.reply_to_id,
                'content': msg.reply_to.content,
                'sender': {
                    'id': msg.reply_to.sender_id,
                    'name': getattr(msg.reply_to.sender, 'name', None),
                    'email': getattr(msg.reply_to.sender, 'email', None),
                },
            }

        forwarded_from = None
        if msg.forwarded_from_id and msg.forwarded_from:
            forwarded_from = {
                'id': msg.forwarded_from_id,
                'content': msg.forwarded_from.content,
                'sender': {
                    'id': msg.forwarded_from.sender_id,
                    'name': getattr(msg.forwarded_from.sender, 'name', None),
                    'email': getattr(msg.forwarded_from.sender, 'email', None),
                },
            }

        reactions = self._serialize_reactions_sync(msg.id, self.scope['user'].id)

        attachments: List[Dict[str, Any]] = []
        for att in getattr(msg, 'attachments', []).all():
            url = att.file.url if att.file else None
            attachments.append(
                {
                    'id': att.id,
                    'kind': att.kind,
                    'url': url,
                    'original_name': att.original_name,
                    'content_type': att.content_type,
                    'size': att.size,
                    'created_at': att.created_at.isoformat() if att.created_at else None,
                }
            )

        return {
            'id': msg.id,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'sender': {
                'id': sender.id,
                'name': getattr(sender, 'name', None),
                'email': getattr(sender, 'email', None),
            },
            'reply_to': reply_to,
            'forwarded_from': forwarded_from,
            'reactions': reactions,
            'attachments': attachments,
        }

    def _serialize_reactions_sync(self, message_id: int, user_id: int) -> List[Dict[str, Any]]:
        # Used when message is already loaded (sync context)
        return self._serialize_reactions(message_id, user_id)

    def _serialize_reactions(self, message_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Aggregate reactions by emoji."""
        qs = (
            ChatReaction.objects.filter(message_id=message_id)
            .values('emoji')
            .annotate(count=Count('id'))
            .order_by('emoji')
        )
        mine = set(
            ChatReaction.objects.filter(message_id=message_id, user_id=user_id)
            .values_list('emoji', flat=True)
        )
        return [{'emoji': r['emoji'], 'count': r['count'], 'me': r['emoji'] in mine} for r in qs]

    def _sync_is_same_target(self, message: ChatMessage) -> bool:
        raise NotImplementedError


class ChannelChatConsumer(BaseChatConsumer):
    channel_id: int

    async def _authorize_and_set_room(self) -> bool:
        self.channel_id = int(self.scope['url_route']['kwargs']['channel_id'])
        user: User = self.scope['user']
        ok = await self._user_in_channel(user.id, self.channel_id)
        if not ok:
            return False
        self.room_group_name = f'chat_channel_{self.channel_id}'
        return True

    async def _get_target_kwargs(self) -> Dict[str, Any]:
        return {'channel_id': self.channel_id, 'group_id': None, 'dm_thread_id': None}

    def _sync_get_target_kwargs(self) -> Dict[str, Any]:
        return {'channel_id': self.channel_id, 'group_id': None, 'dm_thread_id': None}

    async def _is_same_target(self, message: ChatMessage) -> bool:
        return message.channel_id == self.channel_id

    def _sync_is_same_target(self, message: ChatMessage) -> bool:
        return message.channel_id == self.channel_id

    @database_sync_to_async
    def _user_in_channel(self, user_id: int, channel_id: int) -> bool:
        return Channel.objects.filter(id=channel_id, users__id=user_id).exists()


class GroupChatConsumer(BaseChatConsumer):
    group_id: int

    async def _authorize_and_set_room(self) -> bool:
        self.group_id = int(self.scope['url_route']['kwargs']['group_id'])
        user: User = self.scope['user']
        ok = await self._user_in_group(user.id, self.group_id)
        if not ok:
            return False
        self.room_group_name = f'chat_group_{self.group_id}'
        return True

    async def _get_target_kwargs(self) -> Dict[str, Any]:
        return {'channel_id': None, 'group_id': self.group_id, 'dm_thread_id': None}

    def _sync_get_target_kwargs(self) -> Dict[str, Any]:
        return {'channel_id': None, 'group_id': self.group_id, 'dm_thread_id': None}

    async def _is_same_target(self, message: ChatMessage) -> bool:
        return message.group_id == self.group_id

    def _sync_is_same_target(self, message: ChatMessage) -> bool:
        return message.group_id == self.group_id

    @database_sync_to_async
    def _user_in_group(self, user_id: int, group_id: int) -> bool:
        group = Group.objects.filter(id=group_id).first()
        if not group:
            return False

        if group.users.filter(id=user_id).exists():
            return True

        # Allow group creator/admin even if not explicitly added; keep membership consistent.
        if group.group_admin_id == user_id or group.user_id == user_id:
            group.users.add(user_id)
            return True

        return False


class DirectMessageConsumer(BaseChatConsumer):
    other_user_id: int
    thread_id: int

    async def _authorize_and_set_room(self) -> bool:
        self.other_user_id = int(self.scope['url_route']['kwargs']['other_user_id'])
        user: User = self.scope['user']
        if user.id == self.other_user_id:
            return False

        other_exists = await self._user_exists(self.other_user_id)
        if not other_exists:
            return False

        thread = await self._get_or_create_thread(user.id, self.other_user_id)
        self.thread_id = thread
        self.room_group_name = f'chat_dm_{self.thread_id}'
        return True

    async def _get_target_kwargs(self) -> Dict[str, Any]:
        return {'channel_id': None, 'group_id': None, 'dm_thread_id': self.thread_id}

    def _sync_get_target_kwargs(self) -> Dict[str, Any]:
        return {'channel_id': None, 'group_id': None, 'dm_thread_id': self.thread_id}

    async def _is_same_target(self, message: ChatMessage) -> bool:
        return message.dm_thread_id == self.thread_id

    def _sync_is_same_target(self, message: ChatMessage) -> bool:
        return message.dm_thread_id == self.thread_id

    @database_sync_to_async
    def _user_exists(self, user_id: int) -> bool:
        return User.objects.filter(id=user_id, is_active=True).exists()

    @database_sync_to_async
    def _get_or_create_thread(self, user_id: int, other_user_id: int) -> int:
        user1 = User.objects.get(id=user_id)
        user2 = User.objects.get(id=other_user_id)
        thread = DirectMessageThread.get_or_create_for_users(user1, user2)
        return thread.id


class ChatSearchConsumer(AsyncJsonWebsocketConsumer):
    """Search people for chat list (websocket)."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        await self.accept()

    async def receive_json(self, content: Dict[str, Any], **kwargs):
        if content.get('type') != 'people.search':
            await self.send_json({'type': 'error', 'message': 'Unknown event type'})
            return

        query = (content.get('query') or '').strip()
        if not query:
            await self.send_json({'type': 'people.results', 'results': []})
            return

        results = await self._search_people(query=query, me_id=self.scope['user'].id)
        await self.send_json({'type': 'people.results', 'results': results})

    @database_sync_to_async
    def _search_people(self, *, query: str, me_id: int) -> List[Dict[str, Any]]:
        qs = (
            User.objects.filter(is_active=True)
            .exclude(id=me_id)
            .filter(
                Q(email__icontains=query)
                | Q(name__icontains=query)
                | Q(phone_number__icontains=query)
            )
            .order_by('name', 'email')[:20]
        )
        return [
            {
                'id': u.id,
                'name': getattr(u, 'name', None),
                'email': getattr(u, 'email', None),
                'phone_number': getattr(u, 'phone_number', None),
            }
            for u in qs
        ]
