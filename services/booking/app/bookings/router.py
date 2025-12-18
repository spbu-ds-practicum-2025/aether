from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession # Оставьте, это может потребоваться для зависимостей
from app.bookings.schemas import HoldCreateSchema
from app.bookings.repository import BookingRepository, get_booking_repository # <--- РАСКОММЕНТИРОВАНО

router = APIRouter(prefix="/holds", tags=["Holds and Bookings"])

# Роут для создания резерва (Hold)
@router.post("/", status_code=201) # <--- Вернули 201
async def create_new_hold(
    data: HoldCreateSchema,
    repo: BookingRepository = Depends(get_booking_repository) # <--- РАСКОММЕНТИРОВАНО
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