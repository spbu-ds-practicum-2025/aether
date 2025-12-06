from pydantic import BaseModel, root_validator, ValidationError
from datetime import date

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
    available_quantity: int


class SRoomsSearchParams(BaseModel):
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