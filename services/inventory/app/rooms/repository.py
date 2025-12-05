from sqlalchemy import select

from app.database import async_session_maker
from app.rooms.models import RoomTypes
from app.exceptions import RoomNotFoundException


class RoomDAO:

    @classmethod
    async def find_all(cls):
        async with async_session_maker() as session:
            query = select(RoomTypes.__table__.columns)
            rooms = await session.execute(query)
            return rooms.mappings().all()


    @classmethod
    async def find_by_room_type_id(cls, type_id: int):
        async with async_session_maker() as session:
            query = select(RoomTypes.__table__.columns).filter_by(room_type_id=type_id)
            rooms = await session.execute(query)
            rooms = rooms.mappings().all()
            if len(rooms) == 0:
                raise RoomNotFoundException
            return rooms
