from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from authentication.permissions import HasPermission, PermissionConstants, user_has_permission
from Communication.models import Workspace, Channel, DirectMessageThread

from .models import Call, CallParticipant
from .serializers import (
	CallSerializer,
	CreateCallSerializer,
	TokenResponseSerializer,
	CallSummarySerializer,
	CallLogListItemSerializer,
)
from .services.livekit import build_livekit_token


def _assert_context_membership(*, user, context_type: str, workspace=None, channel=None, dm_thread=None) -> None:
	if context_type == 'workspace':
		if not workspace:
			raise ValueError('workspace is required')
		if not (workspace.user_id == user.id or workspace.users.filter(id=user.id).exists()):
			raise PermissionError('You are not a member of this workspace')
	elif context_type == 'channel':
		if not channel:
			raise ValueError('channel is required')
		if not channel.users.filter(id=user.id).exists():
			raise PermissionError('You are not a member of this channel')
	elif context_type == 'dm':
		if not dm_thread:
			raise ValueError('dm_thread is required')
		if user.id not in (dm_thread.user_a_id, dm_thread.user_b_id):
			raise PermissionError('You are not a member of this DM thread')
	else:
		raise ValueError('Invalid context_type')


class CallCreateView(APIView):
	permission_classes = [IsAuthenticated, HasPermission]
	required_permission = PermissionConstants.CALLING

	@extend_schema(
		description='Create a new call (1:1 or group) within a workspace, channel, or DM context.',
		request=CreateCallSerializer,
		responses={201: CallSerializer},
		tags=['Calls'],
	)
	def post(self, request):
		serializer = CreateCallSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		data = serializer.validated_data

		context_type = data['context_type']
		workspace_id = data.get('workspace_id')
		channel_id = data.get('channel_id')
		dm_thread_id = data.get('dm_thread_id')

		workspace = None
		channel = None
		dm_thread = None

		if context_type == 'workspace':
			if not workspace_id:
				return Response({'error': 'workspace_id is required'}, status=status.HTTP_400_BAD_REQUEST)
			workspace = Workspace.objects.get(pk=workspace_id)
		elif context_type == 'channel':
			if not channel_id:
				return Response({'error': 'channel_id is required'}, status=status.HTTP_400_BAD_REQUEST)
			channel = Channel.objects.get(pk=channel_id)
		elif context_type == 'dm':
			if not dm_thread_id:
				return Response({'error': 'dm_thread_id is required'}, status=status.HTTP_400_BAD_REQUEST)
			dm_thread = DirectMessageThread.objects.get(pk=dm_thread_id)

		try:
			_assert_context_membership(
				user=request.user,
				context_type=context_type,
				workspace=workspace,
				channel=channel,
				dm_thread=dm_thread,
			)
		except PermissionError as e:
			return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

		participant_ids = set(data['participant_ids'])
		participant_ids.add(request.user.id)

		# Restrict selectable participants to members of the context.
		if context_type == 'workspace':
			allowed_ids = set(workspace.users.values_list('id', flat=True)) | ({workspace.user_id} if workspace.user_id else set())
		elif context_type == 'channel':
			allowed_ids = set(channel.users.values_list('id', flat=True))
		else:
			allowed_ids = {dm_thread.user_a_id, dm_thread.user_b_id}

		if not participant_ids.issubset(allowed_ids):
			return Response({'error': 'One or more participants are not members of this context'}, status=status.HTTP_400_BAD_REQUEST)

		if context_type == 'dm' and len(participant_ids) != 2:
			return Response({'error': 'DM calls must have exactly 2 participants'}, status=status.HTTP_400_BAD_REQUEST)

		room_name = f"call_{uuid4().hex}"

		with transaction.atomic():
			call = Call.objects.create(
				room_name=room_name,
				created_by=request.user,
				context_type=context_type,
				workspace=workspace,
				channel=channel,
				dm_thread=dm_thread,
				title=data.get('title', ''),
				is_video=data.get('is_video', True),
				is_active=True,
			)
			CallParticipant.objects.bulk_create([
				CallParticipant(call=call, user_id=user_id, invited_by=request.user)
				for user_id in participant_ids
			])

		return Response(CallSerializer(call).data, status=status.HTTP_201_CREATED)


class CallDetailView(APIView):
	permission_classes = [IsAuthenticated, HasPermission]
	required_permission = PermissionConstants.CALLING

	@extend_schema(
		description='Get call details (participants, context, status).',
		responses={200: CallSerializer},
		tags=['Calls'],
	)
	def get(self, request, call_id):
		call = Call.objects.prefetch_related('participants__user').get(pk=call_id)
		if not call.participants.filter(user=request.user).exists():
			return Response({'error': 'Not a participant of this call'}, status=status.HTTP_403_FORBIDDEN)
		return Response(CallSerializer(call).data, status=status.HTTP_200_OK)


class CallTokenView(APIView):
	permission_classes = [IsAuthenticated, HasPermission]
	required_permission = PermissionConstants.CALLING

	@extend_schema(
		description='Issue a LiveKit token for the authenticated user to join the call room.',
		responses={200: TokenResponseSerializer},
		tags=['Calls'],
	)
	def post(self, request, call_id):
		call = Call.objects.get(pk=call_id)
		if not call.is_active:
			return Response({'error': 'Call has ended'}, status=status.HTTP_400_BAD_REQUEST)

		participant = CallParticipant.objects.filter(call=call, user=request.user).first()
		if not participant:
			return Response({'error': 'Not a participant of this call'}, status=status.HTTP_403_FORBIDDEN)

		can_screen_share = user_has_permission(request.user, PermissionConstants.SCREEN_SHARE)

		token_result = build_livekit_token(
			user=request.user,
			room_name=call.room_name,
			can_publish=True,
			can_subscribe=True,
			can_screen_share=can_screen_share,
		)

		if not participant.joined_at:
			participant.joined_at = timezone.now()
			participant.save(update_fields=['joined_at'])

		return Response({
			'call_id': call.id,
			'room_name': call.room_name,
			'livekit_url': getattr(settings, 'LIVEKIT_URL', ''),
			'token': token_result.token,
			'can_screen_share': token_result.can_screen_share,
		}, status=status.HTTP_200_OK)


class CallEndView(APIView):
	permission_classes = [IsAuthenticated, HasPermission]
	required_permission = PermissionConstants.CALLING

	@extend_schema(
		description='End a call (creator only).',
		responses={200: CallSerializer},
		tags=['Calls'],
	)
	def post(self, request, call_id):
		call = Call.objects.get(pk=call_id)
		if call.created_by_id != request.user.id:
			return Response({'error': 'Only the call creator can end the call'}, status=status.HTTP_403_FORBIDDEN)

		if call.is_active:
			call.is_active = False
			call.ended_at = timezone.now()
			call.save(update_fields=['is_active', 'ended_at'])

		return Response(CallSerializer(call).data, status=status.HTTP_200_OK)


def _build_call_summary_payload(call: Call) -> dict:
	participants_qs = call.participants.select_related('user').all()
	total_participants = participants_qs.count()
	joined_participants = participants_qs.filter(joined_at__isnull=False).count()
	left_participants = participants_qs.filter(left_at__isnull=False).count()
	active_participants = participants_qs.filter(joined_at__isnull=False, left_at__isnull=True).count()

	duration_seconds = None
	if call.ended_at:
		duration_seconds = int((call.ended_at - call.started_at).total_seconds())

	return {
		'id': call.id,
		'context_type': call.context_type,
		'workspace_id': call.workspace_id,
		'channel_id': call.channel_id,
		'dm_thread_id': call.dm_thread_id,
		'title': call.title,
		'room_name': call.room_name,
		'is_video': call.is_video,
		'is_active': call.is_active,
		'started_at': call.started_at,
		'ended_at': call.ended_at,
		'duration_seconds': duration_seconds,
		'total_participants': total_participants,
		'joined_participants': joined_participants,
		'left_participants': left_participants,
		'active_participants': active_participants,
		'participants': [
			{
				'user_id': p.user.id,
				'email': p.user.email,
				'name': p.user.name,
				'joined_at': p.joined_at,
				'left_at': p.left_at,
			}
			for p in participants_qs
		],
	}


class CallLeaveView(APIView):
	permission_classes = [IsAuthenticated, HasPermission]
	required_permission = PermissionConstants.CALLING

	@extend_schema(
		description='Mark the authenticated user as having left the call (sets left_at).',
		responses={200: CallSummarySerializer},
		tags=['Calls'],
	)
	def post(self, request, call_id):
		call = Call.objects.get(pk=call_id)
		participant = CallParticipant.objects.filter(call=call, user=request.user).first()
		if not participant:
			return Response({'error': 'Not a participant of this call'}, status=status.HTTP_403_FORBIDDEN)

		if participant.joined_at and not participant.left_at:
			participant.left_at = timezone.now()
			participant.save(update_fields=['left_at'])

		payload = _build_call_summary_payload(call)
		return Response(CallSummarySerializer(payload).data, status=status.HTTP_200_OK)


class CallSummaryView(APIView):
	permission_classes = [IsAuthenticated, HasPermission]
	required_permission = PermissionConstants.CALLING

	@extend_schema(
		description='Get a summary of the call (participant counts, duration, join/leave timestamps).',
		responses={200: CallSummarySerializer},
		tags=['Calls'],
	)
	def get(self, request, call_id):
		call = Call.objects.prefetch_related('participants__user').get(pk=call_id)
		if not call.participants.filter(user=request.user).exists():
			return Response({'error': 'Not a participant of this call'}, status=status.HTTP_403_FORBIDDEN)

		payload = _build_call_summary_payload(call)
		return Response(CallSummarySerializer(payload).data, status=status.HTTP_200_OK)


class CallLogsView(APIView):
	permission_classes = [IsAuthenticated, HasPermission]
	required_permission = PermissionConstants.CALLING

	@extend_schema(
		description='Get call logs (history). Defaults to calls the authenticated user participated in. Optional filters: context_type + workspace_id/channel_id/dm_thread_id.',
		responses={200: CallLogListItemSerializer(many=True)},
		tags=['Calls'],
	)
	def get(self, request):
		context_type = request.query_params.get('context_type')
		workspace_id = request.query_params.get('workspace_id')
		channel_id = request.query_params.get('channel_id')
		dm_thread_id = request.query_params.get('dm_thread_id')

		calls = Call.objects.all().order_by('-started_at')

		if context_type:
			calls = calls.filter(context_type=context_type)
		if workspace_id:
			calls = calls.filter(workspace_id=workspace_id)
		if channel_id:
			calls = calls.filter(channel_id=channel_id)
		if dm_thread_id:
			calls = calls.filter(dm_thread_id=dm_thread_id)

		# Default and safety: only return calls where the user is a participant.
		calls = calls.filter(participants__user=request.user).distinct()

		items = []
		for call in calls:
			duration_seconds = None
			if call.ended_at:
				duration_seconds = int((call.ended_at - call.started_at).total_seconds())
			items.append({
				'id': call.id,
				'context_type': call.context_type,
				'workspace_id': call.workspace_id,
				'channel_id': call.channel_id,
				'dm_thread_id': call.dm_thread_id,
				'title': call.title,
				'is_video': call.is_video,
				'started_at': call.started_at,
				'ended_at': call.ended_at,
				'duration_seconds': duration_seconds,
				'total_participants': call.participants.count(),
			})

		return Response(CallLogListItemSerializer(items, many=True).data, status=status.HTTP_200_OK)

# Create your views here.
