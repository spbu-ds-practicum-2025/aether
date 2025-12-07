from fastapi import APIRouter
from fastapi.params import Depends

from app.rooms.repository import RoomDAO
from app.rooms.schemas import SRooms, SRoomsSearchParams, SRoomsAvailability, SRoomsReservationParams


router = APIRouter(
    prefix="/rooms",
    tags=["Rooms 🏠"]
)


@router.get("")
async def get_rooms() -> list[SRooms]:
    return await RoomDAO.find_all()


@router.get("/search")
async def search(params: SRoomsSearchParams = Depends()) -> list[SRoomsAvailability]:
    return await RoomDAO.search(params)


@router.post("/reserve")
async def reserve(params: SRoomsReservationParams = Depends()):
    return await RoomDAO.add_reservation(params)


@router.post("/release")
async def release(params: SRoomsReservationParams = Depends()):
    return await RoomDAO.del_reservation(params)


@router.get("/{room_type_id}")
async def get_rooms_by_id(room_type_id: str) -> list[SRooms]:
    return await RoomDAO.find_by_room_type_id(room_type_id)