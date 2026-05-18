import json
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class LiveKitTokenResult:
    token: str
    room_name: str
    identity: str
    name: str
    can_screen_share: bool


def build_livekit_token(*, user, room_name: str, can_publish: bool, can_subscribe: bool, can_screen_share: bool) -> LiveKitTokenResult:
    """Create a LiveKit access token for a user to join a given room.

    Note: LiveKit grants do not distinguish screen-share vs camera publish. We include
    `can_screen_share` in token metadata so the client can gate screen-share UI.
    """

    try:
        from livekit.api import AccessToken, VideoGrants
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "LiveKit server SDK is not installed. Install 'livekit-api' (e.g. pip install -r requirements.txt)."
        ) from e

    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise RuntimeError('LiveKit API credentials are not configured')

    identity = str(user.id)
    name = getattr(user, 'name', '') or getattr(user, 'email', '') or identity

    grants = VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=can_publish,
        can_subscribe=can_subscribe,
    )

    metadata = json.dumps({
        'user_id': user.id,
        'email': getattr(user, 'email', None),
        'can_screen_share': bool(can_screen_share),
    })

    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .with_metadata(metadata)
        .to_jwt()
    )

    return LiveKitTokenResult(
        token=token,
        room_name=room_name,
        identity=identity,
        name=name,
        can_screen_share=bool(can_screen_share),
    )
