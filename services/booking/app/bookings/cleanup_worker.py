import asyncio

from app.bookings.repository import BookingRepository
from app.database.engine import AsyncSessionLocal


async def expire_holds_worker(poll_interval_seconds: int = 30) -> None:
    """Periodically expire stale holds so inventory is released."""
    while True:
        try:
            async with AsyncSessionLocal() as session:
                repo = BookingRepository(session)
                expired_ids = await repo.expire_old_holds()
                if expired_ids:
                    print(f"[expire_holds_worker] expired holds: {expired_ids}")
        except Exception as exc:
            print(f"[expire_holds_worker] error: {exc}")
            await asyncio.sleep(10)
            continue

        await asyncio.sleep(poll_interval_seconds)
