from __future__ import annotations

import logging
from typing import List

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from authentication.models import User
from Communication.models import Workspace, Channel, ChatMessage, DirectMessageThread

from .models import Automation, AutomationExecution

logger = logging.getLogger(__name__)


def _get_system_settings():
    # Lazily imported to avoid tight coupling at import time.
    from Notification.models import SystemSettings

    obj, _ = SystemSettings.objects.get_or_create(id=1)
    return obj


def _can_send_email_to_user(*, user: User, category: str) -> bool:
    """Check global + per-user email preferences.

    category:
    - 'direct_messages'
    - 'mentions'
    """
    settings_obj = _get_system_settings()
    if not getattr(settings_obj, 'email_notifications_enabled', True):
        return False

    from Notification.models import NotificationPreference

    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    if category == 'direct_messages':
        return bool(prefs.email_direct_messages)
    if category == 'mentions':
        return bool(prefs.email_mentions)
    # Default deny if category is unknown
    return False


def _can_send_automated_message() -> bool:
    """Check global feature toggle for automated chat messages."""
    settings_obj = _get_system_settings()
    return bool(getattr(settings_obj, 'auto_reply_enabled', True))


def _automation_applies_to_workspace(automation: Automation, workspace: Workspace) -> bool:
    return (automation.workspace_id is None) or (automation.workspace_id == workspace.id)


def _automation_applies_to_channel(automation: Automation, channel: Channel) -> bool:
    if automation.workspace_id is None:
        return True
    return channel.workspaces.filter(id=automation.workspace_id).exists()


@transaction.atomic
def run_user_joins(*, user: User, workspace: Workspace) -> int:
    """Execute enabled automations for the 'user_joins' trigger.

    Returns number of executions attempted.
    """
    automations = Automation.objects.filter(
        is_enabled=True,
        trigger_type=Automation.TRIGGER_USER_JOINS,
    ).select_related('workspace', 'created_by')

    executed = 0

    for automation in automations:
        if not _automation_applies_to_workspace(automation, workspace):
            continue

        executed += 1
        try:
            if automation.action_type == Automation.ACTION_SEND_EMAIL:
                if not _can_send_email_to_user(user=user, category='direct_messages'):
                    continue

                subject = automation.email_subject or automation.name
                body = automation.message_content or ''
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                AutomationExecution.objects.create(
                    automation=automation,
                    workspace=workspace,
                    target_user=user,
                    success=True,
                )

            elif automation.action_type == Automation.ACTION_SEND_MESSAGE:
                if not _can_send_automated_message():
                    continue

                sender = automation.created_by
                if sender is None:
                    # Fallback to workspace creator if no automation creator.
                    sender = workspace.user
                if sender is None:
                    raise ValueError('No sender available for send_message automation')

                thread = DirectMessageThread.get_or_create_for_users(sender, user)
                msg = ChatMessage.objects.create(
                    sender=sender,
                    dm_thread=thread,
                    content=automation.message_content or '',
                )
                AutomationExecution.objects.create(
                    automation=automation,
                    workspace=workspace,
                    message=msg,
                    target_user=user,
                    success=True,
                )
            else:
                raise ValueError(f'Unsupported action_type: {automation.action_type}')

        except Exception as exc:
            logger.exception('Automation user_joins failed')
            AutomationExecution.objects.create(
                automation=automation,
                workspace=workspace,
                target_user=user,
                success=False,
                error=str(exc),
            )

    return executed


@transaction.atomic
def run_new_channel_message(*, message: ChatMessage) -> List[ChatMessage]:
    """Execute enabled automations for the 'new_message' trigger for channel messages.

    Returns a list of auto-generated ChatMessage objects (for broadcasting).
    """
    if not message.channel_id:
        return []

    channel = message.channel
    assert channel is not None

    automations = Automation.objects.filter(
        is_enabled=True,
        trigger_type=Automation.TRIGGER_NEW_MESSAGE,
    ).select_related('workspace', 'created_by')

    created_messages: List[ChatMessage] = []

    for automation in automations:
        if not _automation_applies_to_channel(automation, channel):
            continue

        # Avoid loops: don't auto-reply to messages created by the automation sender.
        if automation.created_by_id and message.sender_id == automation.created_by_id:
            continue

        try:
            if automation.action_type == Automation.ACTION_SEND_MESSAGE:
                if not _can_send_automated_message():
                    continue

                sender = automation.created_by
                if sender is None:
                    raise ValueError('Automation created_by is required for send_message auto-replies')

                reply = ChatMessage.objects.create(
                    sender=sender,
                    channel=channel,
                    content=automation.message_content or '',
                )
                created_messages.append(reply)
                AutomationExecution.objects.create(
                    automation=automation,
                    channel=channel,
                    workspace=automation.workspace if automation.workspace_id else None,
                    message=reply,
                    target_user=message.sender,
                    success=True,
                )

            elif automation.action_type == Automation.ACTION_SEND_EMAIL:
                if not _can_send_email_to_user(user=message.sender, category='mentions'):
                    continue

                subject = automation.email_subject or automation.name
                body = automation.message_content or ''
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[message.sender.email],
                    fail_silently=False,
                )
                AutomationExecution.objects.create(
                    automation=automation,
                    channel=channel,
                    workspace=automation.workspace if automation.workspace_id else None,
                    target_user=message.sender,
                    success=True,
                )
            else:
                raise ValueError(f'Unsupported action_type: {automation.action_type}')

        except Exception as exc:
            logger.exception('Automation new_message failed')
            AutomationExecution.objects.create(
                automation=automation,
                channel=channel,
                workspace=automation.workspace if automation.workspace_id else None,
                target_user=message.sender,
                success=False,
                error=str(exc),
            )

    return created_messages
