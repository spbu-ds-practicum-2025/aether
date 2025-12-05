from fastapi import FastAPI, HTTPException, Query, Depends
import uvicorn
from datetime import date
from pydantic import BaseModel

from app.rooms.router import router as router_rooms

app = FastAPI()

app.include_router(router_rooms)


if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)