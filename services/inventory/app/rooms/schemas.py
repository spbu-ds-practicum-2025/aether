from pydantic import BaseModel, root_validator
from datetime import date
from uuid import UUID
from typing import Literal

from app.exceptions import RoomsValidationPriceException, RoomsValidationDateException


class SRooms(BaseModel):
    room_type_id: str
    name: str
    capacity_adults: int
    price: int
    total_quantity: int

    class Config:
        orm_mode = True


class SRoomsAvailability(SRooms):
    available_quantity: int | None = None


class SRoomsSearchParams(BaseModel):
    room_type_id: str | None = None
    name: str | None = None
    adults: int | None = None
    min_price: int | None = None
    max_price: int | None = None
    check_in: date | None = None
    check_out: date | None = None

    @root_validator
    def check_both_or_none_price(cls, values):
        min_price = values.get('min_price')
        max_price = values.get('max_price')
        check_in = values.get('check_in')
        check_out = values.get('check_out')
        if (min_price is None) != (max_price is None):
            raise RoomsValidationPriceException()
        if (check_in is None) != (check_out is None):
            raise RoomsValidationDateException()
        return values


class SRoomsReservationParams(BaseModel):
    uuid: UUID
    room_type_id: str
    check_in: date
    check_out: date


class SInventoryOperationResult(BaseModel):
    status: Literal['success', 'failure']
    uuid: UUID
    operation: Literal['RESERVE', 'RELEASE']
    room_type_id: str
    check_in: date
    check_out: date
    massage: str | None = None


