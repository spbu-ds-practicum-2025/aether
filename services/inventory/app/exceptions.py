from fastapi import HTTPException, status


class RoomException(HTTPException):
    status_code = 500
    detail = ""

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class RoomNotFoundException(RoomException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Room with that type not exist"