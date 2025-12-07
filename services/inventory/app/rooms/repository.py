from fastapi.openapi.models import Operation
from sqlalchemy import select, and_, func, update

from app.database import async_session_maker
from app.rooms.models import RoomTypes, InventoryDaily, Operations
from app.exceptions import RoomNotFoundException, OperationAlreadyCompletedException, OperationAddFailedException, OperationDelFailedException
from app.rooms.schemas import SRoomsSearchParams, SRoomsReservationParams


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

            if params.room_type_id is not None:
                all_rooms = all_rooms.where(RoomTypes.room_type_id == params.room_type_id)
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


    @classmethod
    async def add_reservation(cls, params: SRoomsReservationParams):
        async with async_session_maker() as session:
            async with session.begin():
                uuid_search = select(Operations.uuid).filter_by(uuid=params.uuid)
                search_result = await session.scalar(uuid_search)

                status = None
                if search_result is not None:
                    operation = select(Operations.status).where(
                        Operations.uuid == params.uuid
                    )
                    status = (await session.execute(operation)).scalar_one_or_none()

                    if status == "SUCCESS":
                        raise OperationAlreadyCompletedException()

                search_params = SRoomsSearchParams(room_type_id=params.room_type_id, check_in=params.check_in, check_out=params.check_out)
                try:
                    room = await RoomDAO.search(search_params)
                except Exception as e:
                    room = None

                if room is not None:
                    available_rooms = room[0]["available_quantity"]
                else:
                    available_rooms = 0

                if available_rooms > 0:
                    reserve = (
                        update(InventoryDaily).where(
                            and_(
                                InventoryDaily.room_type_id == params.room_type_id,
                                InventoryDaily.date >= params.check_in,
                                InventoryDaily.date <= params.check_out
                            )
                        ).values(reserved_quantity = InventoryDaily.reserved_quantity + 1)
                    )
                    if status == "FAILED":
                        operations_update = (
                            update(Operations).where(
                                Operations.uuid == params.uuid
                            ).values(status = "SUCCESS")
                        )
                        await session.execute(operations_update)
                    elif search_result is None:
                        new_operation = Operations(uuid=params.uuid, status="SUCCESS", operation_type="RESERVE", room_type_id=params.room_type_id, check_in=params.check_in, check_out=params.check_out)
                        session.add(new_operation)
                    await session.execute(reserve)
                    await session.commit()
                    return "SUCCESS"
                else:
                    if status == "FAILED":
                        raise OperationAddFailedException
                    elif search_result is None:
                        new_operation = Operations(uuid=params.uuid, status="FAILED", operation_type="RESERVE", room_type_id=params.room_type_id, check_in=params.check_in, check_out=params.check_out)
                        session.add(new_operation)
                        await session.commit()
                        raise OperationAddFailedException


    @classmethod
    async def del_reservation(cls, params: SRoomsReservationParams):
        async with async_session_maker() as session:
            async with session.begin():
                uuid_search = select(Operations.uuid).filter_by(uuid=params.uuid)
                search_result = await session.scalar(uuid_search)

                status = None
                if search_result is not None:
                    operation = select(Operations.status).where(
                        Operations.uuid == params.uuid
                    )
                    status = (await session.execute(operation)).scalar_one_or_none()

                    if status == "SUCCESS":
                        raise OperationAlreadyCompletedException()

                total_quantity = select(RoomTypes.total_quantity).where(
                    RoomTypes.room_type_id == params.room_type_id
                )

                booked_rooms = select(InventoryDaily.__table__.columns).where(
                    and_(
                        InventoryDaily.room_type_id == params.room_type_id,
                        InventoryDaily.date >= params.check_in,
                        InventoryDaily.date <= params.check_out
                    )
                ).cte("booked_rooms")

                min_reserved = select(
                    func.coalesce(func.min(booked_rooms.c.reserved_quantity).label('min_reserved_quantity'), 0)
                )

                min_reserved_num = (await session.execute(min_reserved)).scalar_one_or_none()

                if min_reserved_num > 0:
                    release = (
                        update(InventoryDaily).where(
                            and_(
                                InventoryDaily.room_type_id == params.room_type_id,
                                InventoryDaily.date >= params.check_in,
                                InventoryDaily.date <= params.check_out
                            )
                        ).values(reserved_quantity=InventoryDaily.reserved_quantity - 1)
                    )
                    if status == "FAILED":
                        operations_update = (
                            update(Operations).where(
                                Operations.uuid == params.uuid
                            ).values(status="SUCCESS")
                        )
                        await session.execute(operations_update)
                    elif search_result is None:
                        new_operation = Operations(uuid=params.uuid, status="SUCCESS", operation_type="RELEASE",
                                                   room_type_id=params.room_type_id, check_in=params.check_in,
                                                   check_out=params.check_out)
                        session.add(new_operation)
                    await session.execute(release)
                    await session.commit()
                    return "SUCCESS"
                else:
                    if status == "FAILED":
                        raise OperationDelFailedException
                    elif search_result is None:
                        new_operation = Operations(uuid=params.uuid, status="FAILED", operation_type="RELEASE",
                                                   room_type_id=params.room_type_id, check_in=params.check_in,
                                                   check_out=params.check_out)
                        session.add(new_operation)
                        await session.commit()
                        raise OperationDelFailedException
