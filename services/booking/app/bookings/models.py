import uuid
from sqlalchemy import Column, String, Date, DateTime, func, Index, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB 
from app.database.engine import Base
from sqlalchemy import Column, String, Date, DateTime, func, Index, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB

class Booking(Base):
    __tablename__ = "holds_and_bookings"
    
    # Первичный ключ (UUID), возвращается клиенту
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Ключ для взаимодействия с Inventory Service. Должен быть уникальным
    inventory_op_uuid = Column(UUID(as_uuid=True), unique=True, nullable=False) 

    # Данные бронирования
    user_id = Column(String, nullable=False, index=True)
    room_type_id = Column(String, nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    
    # Статус (HOLD, CONFIRMED, CANCELED, EXPIRED)
    status = Column(String, default="HOLD", nullable=False) 
    
    # TTL (время истечения) для автоматического освобождения
    ttl_expires_at = Column(DateTime, nullable=False, index=True)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        # Индекс для быстрого поиска просроченных резервов
        Index("idx_status_expires", status, ttl_expires_at), 
    )
    
class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)  # Например, "booking_confirmed"
    payload = Column(JSON, nullable=False)       # Сами данные (user_id, email, dates)
    status = Column(String, default="PENDING")   # PENDING, PROCESSED, FAILED
    created_at = Column(DateTime, server_default=func.now())