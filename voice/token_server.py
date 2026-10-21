import os
import structlog
from livekit import api
from typing import Optional

logger = structlog.get_logger()

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://your-project.livekit.cloud")

_token_cache: Optional[str] = None


def create_access_token(identity: str, room: str, metadata: str = "") -> str:
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        logger.warning("LiveKit credentials not configured, returning mock token")
        return "mock_token"
    
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(f"Family Alert - {identity}") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )) \
        .with_metadata(metadata)
    
    return token.to_jwt()


def create_agent_token(agent_name: str, room: str) -> str:
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        return "mock_agent_token"
    
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(f"agent-{agent_name}") \
        .with_name(f"Flood Alert Agent - {agent_name}") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
        ))
    
    return token.to_jwt()


async def create_room(room_name: str, metadata: str = "") -> dict:
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        return {"name": room_name, "sid": "mock_room_sid"}
    
    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        room = await lk_api.room.create_room(api.CreateRoomRequest(
            name=room_name,
            metadata=metadata,
            empty_timeout=300,
            max_participants=10,
        ))
        return {"name": room.name, "sid": room.sid}
    except Exception as e:
        logger.error("Failed to create LiveKit room", error=str(e))
        raise
    finally:
        await lk_api.aclose()


async def delete_room(room_name: str) -> bool:
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        return True
    
    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        return True
    except Exception as e:
        logger.error("Failed to delete LiveKit room", error=str(e))
        return False
    finally:
        await lk_api.aclose()


async def list_rooms() -> list:
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        return []
    
    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())
        return [{"name": r.name, "sid": r.sid, "num_participants": r.num_participants} for r in rooms.rooms]
    except Exception as e:
        logger.error("Failed to list LiveKit rooms", error=str(e))
        return []
    finally:
        await lk_api.aclose()