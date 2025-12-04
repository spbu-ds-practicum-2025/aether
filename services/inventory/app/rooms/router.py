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
