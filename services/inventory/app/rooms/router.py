from fastapi import APIRouter

from app.rooms.repository import RoomDAO
from app.rooms.schemas import SRooms

router = APIRouter(
    prefix="/rooms",
    tags=["Rooms 🏠"]
)

@router.get("")
async def get_rooms() -> list[SRooms]:
    return await RoomDAO.find_all()


@router.get("/{room_type_id}")
async def get_rooms_by_id(room_type_id: str) -> list[SRooms]:
    return await RoomDAO.find_by_room_type_id(room_type_id)
