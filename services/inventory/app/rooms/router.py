from fastapi import APIRouter
from datetime import date

from app.rooms.repository import RoomDAO
from app.rooms.schemas import SRooms

router = APIRouter(
    prefix="/rooms",
    tags=["Rooms 🏠"]
)

@router.get("")
async def get_rooms() -> list[SRooms]:
    return await RoomDAO.find_all()


@router.get("/search")
async def get_rooms_by_id_and_date(type_id: str, check_in: date, check_out: date):
    return await RoomDAO.find_by_type_and_date(type_id, check_in, check_out)


@router.get("/{room_type_id}")
async def get_rooms_by_id(room_type_id: str) -> list[SRooms]:
    return await RoomDAO.find_by_room_type_id(room_type_id)