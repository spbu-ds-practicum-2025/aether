from datetime import date, datetime
from pydantic import BaseModel, Field, validator
from typing import Optional
from uuid import UUID

# Схема для создания нового резерва (Hold)
class HoldCreateSchema(BaseModel):
    # Примечание: user_id должен приходить из системы аутентификации, 
    # но для MVP мы берем его из тела запроса.
    user_id: str = Field(..., description="Идентификатор пользователя, создающего резерв.")
    room_type_id: str = Field(..., description="Тип номера, который нужно зарезервировать.")
    check_in: date = Field(..., description="Дата заезда (включительно).")
    check_out: date = Field(..., description="Дата выезда (не включительно).")

    # Валидация: check_in должен быть раньше check_out
    @validator('check_out')
    def validate_dates(cls, v, values):
        if 'check_in' in values and v <= values['check_in']:
            raise ValueError('check_out must be strictly after check_in date.')
        return v

    class Config:
        # Для работы с datetime.date
        orm_mode = True 
        
# Схема ответа для клиента
class HoldResponseSchema(BaseModel):
    id: UUID
    status: str
    ttl_expires_at: datetime
    
    class Config:
        orm_mode = True