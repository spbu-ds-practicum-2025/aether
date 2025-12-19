import asyncio

from fastapi import FastAPI

from app.bookings.cleanup_worker import expire_holds_worker
from app.bookings.publisher import publish_outbox_events
from app.bookings.router import router as booking_router

app = FastAPI(
    title="Booking Service",
    description="Управление жизненным циклом резервов (Hold) и бронирований.",
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "booking"}


@app.on_event("startup")
async def startup_event():
    # Запускаем фоновые задачи при старте приложения
    asyncio.create_task(publish_outbox_events())
    asyncio.create_task(expire_holds_worker())


# 1. Подключение основного роутера
app.include_router(booking_router, tags=["Holds and Bookings"], prefix="/api/v1")
