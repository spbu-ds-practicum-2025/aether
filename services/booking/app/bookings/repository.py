import os
import uuid
import httpx
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from fastapi import Depends
from app.bookings.models import Booking, OutboxEvent

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
        inventory_op_uuid = uuid.uuid4()
        expires_at = datetime.utcnow() + timedelta(minutes=self.TTL_MINUTES)
        
        # 1. Создаем запись в статусе HOLD, но коммитим её только после Inventory
        new_booking = Booking(
            inventory_op_uuid=inventory_op_uuid,
            user_id=user_id,
            room_type_id=room_type_id,
            check_in=check_in,
            check_out=check_out,
            status="HOLD",
            ttl_expires_at=expires_at
        )
        self.db.add(new_booking)
        await self.db.flush() # Получаем ID, но транзакция еще открыта

        # 2. Запрос к Inventory Service
        inventory_payload = {
            "uuid": str(inventory_op_uuid),
            "room_type_id": room_type_id,
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat()
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{INVENTORY_URL}/rooms/reserve", 
                    json=inventory_payload,
                    timeout=5.0
                )
                response.raise_for_status()
        except Exception as e:
            # Если Inventory недоступен или вернул ошибку — откатываем всё
            await self.db.rollback()
            raise ValueError(f"Inventory reservation failed: {str(e)}")

        # 3. Если всё успешно — коммитим нашу бронь
        await self.db.commit()
        await self.db.refresh(new_booking)
        return new_booking
    
    async def get_all_holds(self, user_id: str = None):
        """Сценарий 4: Получение списка броней."""
        from sqlalchemy import select
        query = select(Booking)
        if user_id:
            query = query.where(Booking.user_id == user_id)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def confirm_booking(self, booking_id: uuid.UUID):
        """Сценарий 3: Подтверждение брони."""
        # 1. Находим бронь и блокируем строку для записи (with_for_update)
        query = select(Booking).where(Booking.id == booking_id).with_for_update()
        result = await self.db.execute(query)
        booking = result.scalar_one_or_none()

        if not booking or booking.status != "HOLD":
            return None # Нельзя подтвердить то, что не в холде

        # 2. Меняем статус
        booking.status = "CONFIRMED"

        # 3. ЗАПИСЫВАЕМ СОБЫТИЕ В OUTBOX (в той же транзакции)
        event = OutboxEvent(
            event_type="booking_confirmed",
            payload={
                "booking_id": str(booking.id),
                "user_id": booking.user_id,
                "room_type_id": booking.room_type_id,
                "check_in": booking.check_in.isoformat(),
                "check_out": booking.check_out.isoformat(),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        self.db.add(event)

        # 4. Фиксируем всё одним коммитом
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def cancel_booking(self, booking_id: uuid.UUID):
        """Сценарий 5: Отмена брони."""
        query = select(Booking).where(Booking.id == booking_id).with_for_update()
        result = await self.db.execute(query)
        booking = result.scalar_one_or_none()

        if not booking or booking.status in ["CANCELED", "EXPIRED"]:
            return booking

        # 1. Запрос в Inventory Service на освобождение (компенсирующее действие)
        # Мы используем сохраненный inventory_op_uuid, чтобы Inventory понял, что это за операция
        release_body = {
            "uuid": str(booking.inventory_op_uuid),
            "room_type_id": booking.room_type_id,
            "check_in": booking.check_in.isoformat(),
            "check_out": booking.check_out.isoformat()
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{INVENTORY_URL}/rooms/release", json=release_body)
                # Если 409 (уже отменено) — это ок, продолжаем. Остальные ошибки стопают процесс.
                if response.status_code != 409:
                    response.raise_for_status()
            except Exception as e:
                # Если инвентори недоступен, мы не можем гарантировать отмену. 
                # В реальных системах тут нужна очередь на переповтор (Retry).
                raise Exception(f"Failed to notify Inventory: {str(e)}")

        # 2. Меняем статус и пишем в Outbox
        booking.status = "CANCELED"
        event = OutboxEvent(
            event_type="booking_cancelled",
            payload={"booking_id": str(booking.id), "user_id": booking.user_id}
        )
        self.db.add(event)
        
        await self.db.commit()
        return booking

    async def expire_old_holds(self):
        """Технический сценарий: безопасная очистка просроченных HOLD."""
        # Используем SKIP LOCKED: если другой экземпляр сервиса уже обрабатывает эти строки, 
        # мы их просто пропустим, а не будем ждать блокировки.
        query = (
            select(Booking.id)
            .where(Booking.status == "HOLD", Booking.ttl_expires_at <= datetime.utcnow())
            .with_for_update(skip_locked=True) 
            .limit(10) # Обрабатываем пачками
        )
        
        result = await self.db.execute(query)
        expired_ids = result.scalars().all()
        
        results = []
        for b_id in expired_ids:
            try:
                # В ТР указано, что просроченные холды переходят в статус EXPIRED
                # Мы вызываем cancel_booking, но внутри можно добавить логику EXPIRED
                await self.cancel_booking(b_id)
                results.append(b_id)
            except Exception as e:
                print(f"Error expiring hold {b_id}: {e}")
        
        return results

async def get_booking_repository(db: AsyncSession = Depends(get_async_session)):
    return BookingRepository(db)