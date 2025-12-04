from pydantic import BaseModel

class SRooms(BaseModel):
    room_type_id: str
    name: str
    capacity_adults: int
    price: int
    total_quantity: int

    class Config:
        orm_mode = True