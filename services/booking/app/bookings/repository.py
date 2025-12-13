import os
import uuid
import httpx
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from fastapi import Depends # <--- ИСПРАВЛЕНИЕ 1: Добавлен импорт Depends

from app.bookings.models import Booking
# ИСПРАВЛЕНИЕ 2: Добавлен импорт get_async_session для функции-зависимости
from app.database.engine import AsyncSessionLocal, get_async_session 
from dotenv import load_dotenv

# Загружаем URL Inventory Service
load_dotenv()
INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL")

class BookingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Время жизни резерва (TTL) - 15 минут
        self.TTL_MINUTES = 15

    async def create_hold(self, user_id: str, room_type_id: str, check_in: date, check_out: date):
        
        # 1. Генерируем UUID для идемпотентности Inventory Service
        inventory_op_uuid = uuid.uuid4()
        expires_at = datetime.utcnow() + timedelta(minutes=self.TTL_MINUTES)
        
        # 2. АТОМАРНОЕ РЕЗЕРВИРОВАНИЕ В ДРУГОМ СЕРВИСЕ
        
        inventory_body = {
            "uuid": str(inventory_op_uuid),
            "room_type_id": room_type_id,
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat()
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Отправляем запрос на блокировку инвентаря
                response = await client.post(
                    f"{INVENTORY_URL}/rooms/reserve", 
                    json=inventory_body
                )
                response.raise_for_status() 
                
            except httpx.HTTPStatusError as e:
                # 409 CONFLICT означает, что инвентаря нет (или идемпотентный повтор failed-операции)
                if e.response.status_code == 409:
                    raise ValueError("Reservation failed: No inventory available for the requested range.")
                
                # Любая другая ошибка (например, 400 Bad Request от Inventory)
                raise e 

        # 3. Если Inventory Service вернул 200/201 (Успешно):
        # Записываем HOLD в нашу Booking DB
        stmt = insert(Booking).values(
            inventory_op_uuid=inventory_op_uuid,
            user_id=user_id,
            room_type_id=room_type_id,
            check_in=check_in,
            check_out=check_out,
            status="HOLD",
            ttl_expires_at=expires_at
        ).returning(Booking.id, Booking.status, Booking.ttl_expires_at)
        
        result = await self.db.execute(stmt)
        await self.db.commit()

        # Получаем данные созданного резерва
        return result.one()

async def get_booking_repository(db: AsyncSession = Depends(get_async_session)):
    return BookingRepository(db)