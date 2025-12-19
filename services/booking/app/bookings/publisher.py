import asyncio
import json
import os
import aio_pika
from sqlalchemy import select, update
from app.database.engine import AsyncSessionLocal
from app.bookings.models import OutboxEvent

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

async def publish_outbox_events():
    """Фоновый воркер для отправки событий из Outbox в RabbitMQ."""
    while True:
        async with AsyncSessionLocal() as session:
            # 1. Получаем пачку необработанных событий
            query = (
                select(OutboxEvent)
                .where(OutboxEvent.status == "PENDING")
                .limit(10)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(query)
            events = result.scalars().all()

            if not events:
                await asyncio.sleep(5) # Если событий нет, спим 5 секунд
                continue

            try:
                # 2. Подключаемся к RabbitMQ
                connection = await aio_pika.connect_robust(RABBITMQ_URL)
                async with connection:
                    channel = await connection.channel()
                    
                    # Объявляем очередь (notifications — это тот, кто будет слушать)
                    queue = await channel.declare_queue("booking_notifications", durable=True)

                    for event in events:
                        # 3. Публикуем сообщение
                        message_body = json.dumps({
                            "event_type": event.event_type,
                            "payload": event.payload
                        }).encode()

                        await channel.default_exchange.publish(
                            aio_pika.Message(
                                body=message_body,
                                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                            ),
                            routing_key="booking_notifications",
                        )

                        # 4. Помечаем как отправленное
                        event.status = "PROCESSED"
                    
                    await session.commit()
                    print(f"Published {len(events)} events to RabbitMQ")

            except Exception as e:
                print(f"Error publishing events: {e}")
                await session.rollback()
                await asyncio.sleep(10) # При ошибке ждем дольше