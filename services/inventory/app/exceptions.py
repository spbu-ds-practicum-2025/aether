from fastapi import HTTPException, status


class RoomException(HTTPException):
    status_code = 500
    detail = ""

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class RoomNotFoundException(RoomException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "No available rooms with specified parameters was found."


class RoomsValidationPriceException(RoomException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Fields 'min_price' and 'max_price' must be specified both or none."


class RoomsValidationDateException(RoomException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Fields 'check_in' and 'check_out' must be specified both or none."


class OperationException(HTTPException):
    status_code = 500
    detail = {
        "status": "",
        "msg": ""
    }

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class OperationAlreadyCompletedException(OperationException):
    status_code = status.HTTP_409_CONFLICT
    detail = {
        "status": "success",
        "msg": "Operation already completed."
    }


class OperationAddFailedException(OperationException):
    status_code = status.HTTP_409_CONFLICT
    detail = {
        "status": "fail",
        "msg": "Operation failed, no available rooms."
    }


class OperationDelFailedException(OperationException):
    status_code = status.HTTP_409_CONFLICT
    detail = {
        "status": "fail",
        "msg": "Operation failed, no rooms to release."
    }