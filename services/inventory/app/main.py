from fastapi import FastAPI
import uvicorn

from app.rooms.router import router as router_rooms


app = FastAPI()

app.include_router(router_rooms)


if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)