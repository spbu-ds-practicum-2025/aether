import asyncio
import sys
import selectors
from app.database.engine import engine, Base
from app.bookings.models import Booking, OutboxEvent

async def main():
    print("Подключение к базе в Docker...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Таблицы успешно созданы!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        loop_factory = lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.run(main(), loop_factory=loop_factory)
    else:
        asyncio.run(main())