from app.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, func
from sqlalchemy.dialects.postgresql import UUID


class RoomTypes(Base):
    __tablename__ = "room_types"

    room_type_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    capacity_adults = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    total_quantity = Column(Integer, nullable=False)


class InventoryDaily(Base):
    __tablename__ = "inventory_daily"

    id = Column(Integer, primary_key=True)
    room_type_id = Column(ForeignKey("room_types.room_type_id"))
    date = Column(Date, nullable=False)
    reserved_quantity = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Operations(Base):
    __tablename__ = "operations"

    uuid = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    status = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)
    room_type_id = Column(ForeignKey("room_types.room_type_id"))
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)