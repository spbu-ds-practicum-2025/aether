from fastapi import FastAPI
from app.bookings.router import router as booking_router
import asyncio
from app.bookings.publisher import publish_outbox_events

app = FastAPI(
    title="Booking Service",
    description="Управление жизненным циклом резервов (Hold) и бронирований.",
    version="1.0.0",
)

@app.get("/health")
def health_check():
    """Проверка работоспособности сервиса."""
    return {"status": "ok", "service": "booking"}

@app.on_event("startup")
async def startup_event():
    # Запускаем воркер в фоне, чтобы он не блокировал основной поток API
    asyncio.create_task(publish_outbox_events())

# 1. Подключение роутеров
app.include_router(booking_router, tags=["Holds and Bookings"], prefix="/api/v1")