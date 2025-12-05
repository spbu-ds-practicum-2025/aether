from sqlalchemy import select, and_, or_, func, true

from app.database import async_session_maker
from app.rooms.models import RoomTypes, InventoryDaily
from app.exceptions import RoomNotFoundException

from datetime import date


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

    @classmethod
    async def find_by_type_and_date(cls, type_id: str, check_in: date, check_out: date):
        """
        WITH booked_rooms AS (
            SELECT * FROM inventory_daily
            WHERE room_type_id = 'DELUXE_A' AND
            date >= '2025-12-05' AND date <= '2025-12-10'
        ),

        max_reserved AS (
            SELECT MAX(reserved_quantity) AS max_reserved_quantity
            FROM booked_rooms
        )

        SELECT room_types.total_quantity - max_reserved.max_reserved_quantity
        AS total_available
        FROM room_types
        CROSS JOIN max_reserved
        WHERE room_types.room_type_id = 'DELUXE_A'
        """
        async with async_session_maker() as session:
            booked_rooms = select(InventoryDaily.__table__.columns).where(
                and_(
                    InventoryDaily.room_type_id == type_id,
                    InventoryDaily.date >= check_in,
                    InventoryDaily.date <= check_out
                )
            ).cte("booked_rooms")
            max_reserved = select(
                func.max(booked_rooms.c.reserved_quantity).label('max_reserved_quantity')
            ).cte("max_reserved")
            query = (
                select(
                    RoomTypes.total_quantity - max_reserved.c.max_reserved_quantity
                ).select_from(RoomTypes).join(
                    max_reserved, true()
                ).where(
                    RoomTypes.room_type_id == type_id
                )
            )

            rooms_left = await session.execute(query)
            return rooms_left.mappings().all()


