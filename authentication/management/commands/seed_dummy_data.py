"""Seed dummy workspace/chat/message/notification data for two users.

Usage:
    python manage.py seed_dummy_data

Optional:
    python manage.py seed_dummy_data --primary-email user1@example.com --secondary-email user2@example.com

This command is idempotent: re-running it will not duplicate seeded messages/notifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, List, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from authentication.models import User

from Communication.models import (
    Channel,
    ChatMessage,
    ChatReaction,
    DirectMessageThread,
    Group,
    Workspace,
)
from Notification.models import Notification, NotificationPreference, SystemSettings
from Notification.services import create_notification_for_user


@dataclass(frozen=True)
class SeedSpec:
    primary_email: str
    secondary_email: str
    seed_prefix: str


class Command(BaseCommand):
    help = "Seed dummy data (workspaces/channels/messages/notifications) for two users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--primary-email",
            default="havime5142@bmoar.com",
            help="Primary user email to seed data for (default: havime5142@bmoar.com)",
        )
        parser.add_argument(
            "--secondary-email",
            default="abrarzaved2002@gmail.com",
            help="Secondary user email to seed data with (default: abrarzaved2002@gmail.com)",
        )
        parser.add_argument(
            "--broadcast",
            action="store_true",
            help="Broadcast notifications over websocket while seeding (default: off)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        primary_email: str = options["primary_email"].strip().lower()
        secondary_email: str = options["secondary_email"].strip().lower()
        broadcast: bool = bool(options.get("broadcast", False))

        if primary_email == secondary_email:
            raise ValueError("primary-email and secondary-email must be different")

        spec = SeedSpec(
            primary_email=primary_email,
            secondary_email=secondary_email,
            seed_prefix=f"[seed_dummy_data:v1:{primary_email}:{secondary_email}]",
        )

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding dummy data..."))
        self.stdout.write(f"Primary: {spec.primary_email}")
        self.stdout.write(f"Secondary: {spec.secondary_email}")

        primary_user = self._get_or_create_user(spec.primary_email, name="Havime (Demo)")
        secondary_user = self._get_or_create_user(spec.secondary_email, name="Abrar (Demo)")

        self._ensure_notification_defaults(users=[primary_user, secondary_user])

        workspace, channels, group = self._get_or_create_communication_graph(
            primary_user=primary_user,
            secondary_user=secondary_user,
            spec=spec,
        )

        dm_thread = DirectMessageThread.get_or_create_for_users(primary_user, secondary_user)

        created_messages = 0
        created_messages += self._seed_channel_messages(
            spec=spec,
            channel=channels[0],
            users=(primary_user, secondary_user),
            count=10,
        )
        created_messages += self._seed_channel_messages(
            spec=spec,
            channel=channels[1],
            users=(secondary_user, primary_user),
            count=6,
        )
        created_messages += self._seed_group_messages(
            spec=spec,
            group=group,
            users=(primary_user, secondary_user),
            count=6,
        )
        created_messages += self._seed_dm_messages(
            spec=spec,
            dm_thread=dm_thread,
            users=(primary_user, secondary_user),
            count=12,
        )

        created_reactions = self._seed_reactions(spec=spec, users=(primary_user, secondary_user))
        created_notifications = self._seed_notifications(
            spec=spec,
            primary_user=primary_user,
            secondary_user=secondary_user,
            workspace=workspace,
            dm_thread=dm_thread,
            broadcast=broadcast,
        )

        self.stdout.write(self.style.SUCCESS("\nDone."))
        self.stdout.write(
            self.style.SUCCESS(
                f"Created messages: {created_messages} | reactions: {created_reactions} | notifications: {created_notifications}"
            )
        )

    def _get_or_create_user(self, email: str, *, name: str) -> User:
        user = User.objects.filter(email=email).first()
        if user:
            return user

        # Create with an unusable password for safety.
        user = User.objects.create(email=email, name=name, is_verified=True, is_active=True)
        user.set_unusable_password()
        user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS(f"✓ Created user: {email}"))
        return user

    def _ensure_notification_defaults(self, *, users: Iterable[User]) -> None:
        SystemSettings.objects.get_or_create(id=1)
        for user in users:
            prefs, _ = NotificationPreference.objects.get_or_create(user=user)
            # Ensure push is on so Notification.services will actually store rows.
            changed = False
            if not prefs.push_mobile_notifications:
                prefs.push_mobile_notifications = True
                changed = True
            if changed:
                prefs.save(update_fields=["push_mobile_notifications"])

    def _get_or_create_communication_graph(
        self,
        *,
        primary_user: User,
        secondary_user: User,
        spec: SeedSpec,
    ) -> Tuple[Workspace, List[Channel], Group]:
        workspace_name = f"Demo Workspace ({primary_user.email.split('@')[0]} & {secondary_user.email.split('@')[0]})"
        workspace, workspace_created = Workspace.objects.get_or_create(
            name=workspace_name,
            defaults={"user": primary_user, "is_active": True},
        )
        if workspace_created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created workspace: {workspace.name}"))

        channel_general, cg_created = Channel.objects.get_or_create(
            name=f"demo-general-{primary_user.id}-{secondary_user.id}",
            defaults={"user": primary_user, "type": "public", "is_active": True},
        )
        if cg_created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created channel: {channel_general.name}"))

        channel_random, cr_created = Channel.objects.get_or_create(
            name=f"demo-random-{primary_user.id}-{secondary_user.id}",
            defaults={"user": secondary_user, "type": "private", "is_active": True},
        )
        if cr_created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created channel: {channel_random.name}"))

        group, group_created = Group.objects.get_or_create(
            name=f"Demo Group ({primary_user.id}-{secondary_user.id})",
            defaults={"user": primary_user, "group_admin": secondary_user, "is_active": True},
        )
        if group_created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created group: {group.name}"))

        # Memberships
        workspace.users.add(primary_user, secondary_user)
        workspace.channels.add(channel_general, channel_random)

        channel_general.users.add(primary_user, secondary_user)
        channel_random.users.add(primary_user, secondary_user)

        group.users.add(primary_user, secondary_user)

        return workspace, [channel_general, channel_random], group

    def _seed_channel_messages(self, *, spec: SeedSpec, channel: Channel, users: Tuple[User, User], count: int) -> int:
        seed_key = f"{spec.seed_prefix}:channel:{channel.id}:"
        if ChatMessage.objects.filter(channel=channel, content__startswith=seed_key).exists():
            return 0

        now = timezone.now()
        created = 0
        previous: ChatMessage | None = None
        for i in range(count):
            sender = users[i % 2]
            content = f"{seed_key}{i} {sender.email}: Hello in #{channel.name} (msg {i + 1}/{count})"
            msg = ChatMessage.objects.create(
                sender=sender,
                channel=channel,
                content=content,
                reply_to=previous if i == 3 else None,
                created_at=now - timedelta(minutes=(count - i) * 5),
                updated_at=now - timedelta(minutes=(count - i) * 5),
            )
            if i == 2:
                previous = msg
            created += 1
        return created

    def _seed_group_messages(self, *, spec: SeedSpec, group: Group, users: Tuple[User, User], count: int) -> int:
        seed_key = f"{spec.seed_prefix}:group:{group.id}:"
        if ChatMessage.objects.filter(group=group, content__startswith=seed_key).exists():
            return 0

        now = timezone.now()
        created = 0
        for i in range(count):
            sender = users[(i + 1) % 2]
            content = f"{seed_key}{i} {sender.email}: Group update {i + 1}/{count}"
            ChatMessage.objects.create(
                sender=sender,
                group=group,
                content=content,
                created_at=now - timedelta(minutes=(count - i) * 7),
                updated_at=now - timedelta(minutes=(count - i) * 7),
            )
            created += 1
        return created

    def _seed_dm_messages(
        self,
        *,
        spec: SeedSpec,
        dm_thread: DirectMessageThread,
        users: Tuple[User, User],
        count: int,
    ) -> int:
        seed_key = f"{spec.seed_prefix}:dm:{dm_thread.id}:"
        if ChatMessage.objects.filter(dm_thread=dm_thread, content__startswith=seed_key).exists():
            return 0

        now = timezone.now()
        created = 0
        root: ChatMessage | None = None
        for i in range(count):
            sender = users[i % 2]
            content = f"{seed_key}{i} {sender.email}: DM ping {i + 1}/{count}"
            msg = ChatMessage.objects.create(
                sender=sender,
                dm_thread=dm_thread,
                content=content,
                reply_to=root if i == 4 else None,
                forwarded_from=root if i == 7 else None,
                created_at=now - timedelta(minutes=(count - i) * 3),
                updated_at=now - timedelta(minutes=(count - i) * 3),
            )
            if i == 1:
                root = msg
            created += 1
        return created

    def _seed_reactions(self, *, spec: SeedSpec, users: Tuple[User, User]) -> int:
        # Add a few reactions to the newest seeded messages (if any) across DM.
        created = 0

        # Find any seeded messages.
        messages = list(
            ChatMessage.objects.filter(content__startswith=spec.seed_prefix)
            .order_by("-created_at")
            .only("id")[:5]
        )
        if not messages:
            return 0

        emojis = ["👍", "🎉", "😂"]
        for idx, message in enumerate(messages):
            user = users[idx % 2]
            emoji = emojis[idx % len(emojis)]
            _, was_created = ChatReaction.objects.get_or_create(message=message, user=user, emoji=emoji)
            if was_created:
                created += 1
        return created

    def _seed_notifications(
        self,
        *,
        spec: SeedSpec,
        primary_user: User,
        secondary_user: User,
        workspace: Workspace,
        dm_thread: DirectMessageThread,
        broadcast: bool,
    ) -> int:
        seed_title_prefix = f"{spec.seed_prefix} "

        def _already(user: User, suffix: str) -> bool:
            return Notification.objects.filter(user=user, title=seed_title_prefix + suffix).exists()

        created = 0

        # Primary gets a few notifications, mostly triggered by secondary.
        notifications_primary = [
            (
                "direct_message",
                "New DM from Abrar",
                {
                    "from_user_email": secondary_user.email,
                    "dm_thread_id": dm_thread.id,
                },
            ),
            (
                "mention",
                "You were mentioned in demo-general",
                {
                    "from_user_email": secondary_user.email,
                    "workspace_id": workspace.id,
                },
            ),
            (
                "channel_invite",
                "Added to demo-random",
                {
                    "from_user_email": secondary_user.email,
                    "workspace_id": workspace.id,
                },
            ),
        ]

        for n_type, suffix, data in notifications_primary:
            if _already(primary_user, suffix):
                continue
            n = create_notification_for_user(
                user=primary_user,
                notification_type=n_type,
                title=seed_title_prefix + suffix,
                body=f"{suffix} (seeded)",
                data=data,
                broadcast=broadcast,
            )
            if n is not None:
                created += 1

        # Secondary gets one notification from primary.
        if not _already(secondary_user, "New DM from Havime"):
            n = create_notification_for_user(
                user=secondary_user,
                notification_type="direct_message",
                title=seed_title_prefix + "New DM from Havime",
                body="New DM (seeded)",
                data={"from_user_email": primary_user.email, "dm_thread_id": dm_thread.id},
                broadcast=broadcast,
            )
            if n is not None:
                created += 1

        # Mark one as read for realism.
        unread = Notification.objects.filter(user=primary_user, title__startswith=seed_title_prefix, is_read=False)
        first = unread.order_by("created_at").first()
        if first:
            first.is_read = True
            first.read_at = timezone.now()
            first.save(update_fields=["is_read", "read_at"])

        return created
