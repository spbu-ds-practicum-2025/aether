from datetime import date, datetime
from pydantic import BaseModel, Field, validator
from typing import Optional
from uuid import UUID

# Схема для создания нового резерва (Hold)
class HoldCreateSchema(BaseModel):
    user_id: str
    room_type_id: str
    check_in: date
    check_out: date

    @validator('check_in')
    def check_in_not_in_past(cls, v):
        if v < date.today():
            raise ValueError('check_in date cannot be in the past.')
        return v

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