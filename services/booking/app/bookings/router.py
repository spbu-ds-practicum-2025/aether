from fastapi import APIRouter, HTTPException, Depends
import uuid
# Добавьте явный импорт схемы:
from app.bookings.schemas import HoldCreateSchema, HoldResponseSchema 
from app.bookings.repository import BookingRepository, get_booking_repository

router = APIRouter(prefix=\"/holds\", tags=[\"Holds and Bookings\"])

# Роут для создания резерва (Hold)
@router.post("/", status_code=201)
async def create_new_hold(
    data: HoldCreateSchema,
    repo: BookingRepository = Depends(get_booking_repository)
):
    """
    Создает временный резерв (HOLD) в Booking Service и атомарно 
    резервирует инвентарь в Inventory Service.
    """
    try: 
        # repo.create_hold выполняет HTTP-запрос и запись в DB
        hold_data = await repo.create_hold(
            data.user_id,
            data.room_type_id,
            data.check_in,
            data.check_out
        )
        
        # Преобразование результата DB в схему ответа
        return {
            "id": hold_data.id, 
            "status": hold_data.status, 
            "ttl_expires_at": hold_data.ttl_expires_at
        }
        
    except ValueError as e:
        # Возвращаем 409, если нет доступности (пришло от Inventory Service)
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        # Для других непредвиденных ошибок
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    
@router.get("/", response_model=list[HoldResponseSchema])
async def get_holds(
    user_id: str = None,
    repo: BookingRepository = Depends(get_booking_repository)
):
    """Возвращает список броней пользователя (Сценарий 4 из ТР)."""
    return await repo.get_all_holds(user_id)

@router.post("/{hold_id}/confirm")
async def confirm_hold(
    hold_id: uuid.UUID,
    repo: BookingRepository = Depends(get_booking_repository)
):
    """Подтверждение брони (Сценарий 3 из ТР)."""
    updated = await repo.confirm_booking(hold_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Hold not found or already confirmed")
    return {"id": updated.id, "status": updated.status}

@router.post("/{hold_id}/cancel")
async def cancel_hold(
    hold_id: uuid.UUID,
    repo: BookingRepository = Depends(get_booking_repository)
):
    """Отмена брони (Сценарий 5 из ТР)."""
    cancelled = await repo.cancel_booking(hold_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Booking not found or already cancelled")
    return {"id": cancelled.id, "status": cancelled.status}

@router.post("/internal/expire")
async def expire_holds(
    repo: BookingRepository = Depends(get_booking_repository)
):
    """
    Технический эндпоинт для запуска очистки. 
    В реальной жизни его будет дергать Cron или специальный Task Scheduler.
    """
    expired_ids = await repo.expire_old_holds()
    return {"status": "success", "expired_count": len(expired_ids), "ids": expired_ids}