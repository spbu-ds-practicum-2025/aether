from fastapi import FastAPI
from app.bookings.router import router as booking_router # Раскомментируем

app = FastAPI(
    title="Booking Service",
    description="Управление жизненным циклом резервов (Hold) и бронирований.",
    version="1.0.0",
)

@app.get("/health")
def health_check():
    """Проверка работоспособности сервиса."""
    return {"status": "ok", "service": "booking"}

# 1. Подключение роутеров
app.include_router(booking_router, tags=["Holds and Bookings"], prefix="/api/v1")