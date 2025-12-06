from sqlalchemy import select, and_, or_, func, true

from app.database import async_session_maker
from app.rooms.models import RoomTypes, InventoryDaily
from app.exceptions import RoomNotFoundException
from app.rooms.schemas import SRoomsSearchParams

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
    async def search(cls, params: SRoomsSearchParams):
        async with async_session_maker() as session:

            all_rooms = select(RoomTypes.__table__.columns)

            if params.name is not None:
                all_rooms = all_rooms.where(RoomTypes.name == params.name)
            if params.adults is not None:
                all_rooms = all_rooms.where(RoomTypes.capacity_adults >= params.adults)
            if params.min_price is not None:
                all_rooms = all_rooms.where(
                    and_(
                        RoomTypes.price >= params.min_price,
                        RoomTypes.price <= params.max_price
                    )
                )

            if params.check_in is not None:
                all_rooms = all_rooms.cte("all_rooms")

                booked_rooms = select(InventoryDaily.__table__.columns).where(
                    and_(
                        InventoryDaily.room_type_id.in_(select(all_rooms.c.room_type_id)),
                        InventoryDaily.date >= params.check_in,
                        InventoryDaily.date <= params.check_out
                    )
                ).cte("booked_rooms")

                max_reserved = select(
                    booked_rooms.c.room_type_id,
                    func.max(booked_rooms.c.reserved_quantity).label('max_reserved_quantity')
                ).group_by(booked_rooms.c.room_type_id).cte("max_reserved")

                query = (
                    select(
                        all_rooms,
                        (
                                all_rooms.c.total_quantity
                                - func.coalesce(max_reserved.c.max_reserved_quantity, 0)
                        ).label("available_quantity"),
                    )
                    .select_from(all_rooms)
                    .join(
                        max_reserved,
                        max_reserved.c.room_type_id == all_rooms.c.room_type_id,
                        isouter=True,
                    )
                    .where(
                        all_rooms.c.total_quantity
                        - func.coalesce(max_reserved.c.max_reserved_quantity, 0) > 0
                    )
                )

                rooms = await session.execute(query)
            else:
                rooms = await session.execute(all_rooms)

            rooms = rooms.mappings().all()
            if len(rooms) == 0:
                raise RoomNotFoundException()

            return rooms

