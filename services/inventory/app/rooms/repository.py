from sqlalchemy import select

from app.database import async_session_maker
from app.rooms.models import RoomTypes


class RoomDAO:

    @classmethod
    async def find_all(cls):
        async with async_session_maker() as session:
            query = select(RoomTypes.__table__.columns)
            rooms = await session.execute(query)
            return rooms.mappings().all()


    # @classmethod
    # async def find_by_date(cls, check_in, check_out):
    #     async with async_session_maker() as session: