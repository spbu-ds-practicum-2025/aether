import os
import uuid
import httpx
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from fastapi import Depends 

from app.bookings.models import Booking
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
    
    async def get_all_holds(self, user_id: str = None):
        """Получение списка всех броней. Если передан user_id — фильтруем по нему."""
        from sqlalchemy import select
        query = select(Booking)
        if user_id:
            query = query.where(Booking.user_id == user_id)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def confirm_booking(self, hold_id: uuid.UUID):
        """Сценарий 3: Перевод резерва в статус подтвержденной брони."""
        from sqlalchemy import update
        stmt = (
            update(Booking)
            .where(Booking.id == hold_id, Booking.status == "HOLD")
            .values(status="CONFIRMED")
            .returning(Booking.id, Booking.status)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.one_or_none()
    
    async def cancel_booking(self, hold_id: uuid.UUID):
        """Сценарий 5: Отмена брони и вызов Inventory для освобождения дат."""
        from sqlalchemy import select, update
        
        # 1. Находим бронь, чтобы получить данные для Inventory Service
        query = select(Booking).where(Booking.id == hold_id)
        booking = (await self.db.execute(query)).scalar_one_or_none()
        
        if not booking or booking.status == "CANCELED":
            return None

        # 2. Вызов Inventory Service (release)
        async with httpx.AsyncClient() as client:
            release_body = {
                "uuid": str(booking.inventory_op_uuid),
                "room_type_id": booking.room_type_id,
                "check_in": booking.check_in.isoformat(),
                "check_out": booking.check_out.isoformat()
            }
            response = await client.post(
                f"{INVENTORY_URL}/rooms/release", 
                json=release_body
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Inventory release failed: {response.text}")

        booking.status = "CANCELED"
        await self.db.commit()
        return booking
    
    async def expire_old_holds(self):
        """Технический сценарий: поиск и отмена просроченных HOLD."""
        from sqlalchemy import select
        # 1. Ищем все просроченные HOLD (используем ваш индекс idx_status_expires)
        query = select(Booking).where(
            Booking.status == "HOLD",
            Booking.ttl_expires_at <= datetime.utcnow()
        )
        expired_bookings = (await self.db.execute(query)).scalars().all()
        
        results = []
        for b in expired_bookings:
            # Для каждого вызываем release в Inventory и ставим EXPIRED
            try:
                await self.cancel_booking(b.id) # Переиспользуем логику отмены
                b.status = "EXPIRED"
                results.append(b.id)
            except Exception as e:
                print(f"Failed to expire {b.id}: {e}")
        
        await self.db.commit()
        return results

async def get_booking_repository(db: AsyncSession = Depends(get_async_session)):
    return BookingRepository(db)