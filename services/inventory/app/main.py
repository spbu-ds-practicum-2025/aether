from fastapi import FastAPI, HTTPException, Query, Depends
import uvicorn
from datetime import date
from pydantic import BaseModel


app = FastAPI()


class Room(BaseModel):
    room_type_id: str
    price: int
    num_of_guests: int


class RoomSearchArgs:
    def __init__(
            self,
            date_from: date,
            date_to: date,
            price: int | None = None,
            room_type_id: str | None = None,
            num_of_guests: int | None = Query(None, ge=1, le=6),
    ):
        self.date_from = date_from
        self.date_to = date_to
        self.price = price
        self.room_type_id = room_type_id
        self.num_of_guests = num_of_guests


@app.get("/rooms",
         tags=["rooms 🚪"],
         summary="Get all rooms",)
def search(
        search_args: RoomSearchArgs = Depends()
        ) -> list[Room]:

    rooms = [
        {
            "room_type_id": "DELUXE_A",
            "price": 5000,
            "num_of_guests": 3,
        }
    ]
    return rooms


@app.get("/rooms/{room_id}",
         tags=["rooms 🚪"],
         summary="Get one room",)
def get_room(room_id: int):
    for room in rooms:
        if room["room_id"] == room_id:
            return room
    return HTTPException(status_code=404, detail="Room not found")


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)