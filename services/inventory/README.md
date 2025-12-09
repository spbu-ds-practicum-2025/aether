# Inventory Service Documentation

Distributed hotel room availability service for hotel room types: search, reserve, and release inventory with FastAPI, PostgreSQL, SQLAlchemy (async), and Alembic migrations.

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 15+
- Bash (scripts/app.sh)
- Docker (optional; provided compose for local run)

### Run the Service Locally

```bash
# 1. Install dependencies
cd services/inventory
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Start PostgreSQL (example via Docker)
docker run -d --name inventory-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=inventory_app \
  -p 5432:5432 \
  postgres:15

# 3. Configure environment
# Create .env with DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
# (use your local values; avoid committing secrets)

# 4. Run migrations
alembic upgrade head

# 5. (Optional) Seed sample data
psql "postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME" -f data/room_types_data.sql
psql "postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME" -f data/test_inventory_daily_data.sql

# 6. Start the API (dev)
uvicorn app.main:app --reload --port 8000
```

Service listens on `http://localhost:8000` by default.

### Run with Docker Compose

```bash
cd services/inventory
docker compose up --build
```

- PostgreSQL starts as `inventory_db` using credentials from `.env-non-dev` (required for compose; keep secrets there).
- API runs in `inventory_app` via `scripts/app.sh`, published on host port `9000` (container port `8000`).
Notes:
- `.env-non-dev` is required for Compose and contains DB credentials for the app and PostgreSQL container; do not commit or expose its contents.
- For local (non-Docker) runs, create your own `.env` with the same variable names.

### `.env-non-dev` structure (for Docker Compose)

Create `services/inventory/.env-non-dev` with the following keys (set your own values):

```dotenv
DB_HOST=db
DB_PORT=5432
DB_USER=<db-user>
DB_PASS=<db-password>
DB_NAME=<db-name>

POSTGRES_DB=<db-name>
POSTGRES_USER=<db-user>
POSTGRES_PASSWORD=<db-password>
```

`.env` for local runs uses the same variable names but should point to your local PostgreSQL instance.

### Smoke Test (search available rooms)

```bash
curl "http://localhost:8000/rooms/search?adults=2&min_price=4000&max_price=15000&check_in=2025-12-10&check_out=2025-12-12"
```

---

## Architecture

### Layers

```
[ FastAPI (app.main, app.rooms.router) ]
        ↓
[ RoomDAO / SQLAlchemy Core (app.rooms.repository) ]
        ↓
[ Async engine + session (app.database) ]
        ↓
[ PostgreSQL + Alembic migrations ]
```

### Key Components

**API Layer** (`app/main.py`, `app/rooms/router.py`)
- FastAPI app with `/rooms` endpoints.
- Request parameter parsing via Pydantic v1 schemas.

**Data Access** (`app/rooms/repository.py`)
- Async SQLAlchemy Core queries (no ORM session models in handlers).
- Business rules for availability search, reservation, and release.
- Idempotency via `operations.uuid`.

**Persistence** (`app/database.py`, `app/rooms/models.py`)
- Async engine (`create_async_engine`) and session maker.
- Declarative models for `room_types`, `inventory_daily`, `operations`.
- Alembic migrations in `app/migrations`.

**App Runtime**
- Dev: `uvicorn app.main:app --reload`.
- Prod/compose: `gunicorn` via `scripts/app.sh` (`uvicorn.workers.UvicornWorker`, 4 workers).

---

## Database Schema

### Tables

**room_types**
```sql
room_type_id   VARCHAR PRIMARY KEY
name           VARCHAR NOT NULL          -- logical name (econom, deluxe, etc.)
capacity_adults INTEGER NOT NULL
price          INTEGER NOT NULL         -- per-night price (no currency conversion)
total_quantity INTEGER NOT NULL         -- total rooms of this type
```

**inventory_daily**
```sql
id               SERIAL PRIMARY KEY
room_type_id     VARCHAR REFERENCES room_types(room_type_id)
date             DATE NOT NULL
reserved_quantity INTEGER NOT NULL      -- number of rooms already reserved
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now() ON UPDATE now()
UNIQUE (room_type_id, date)
```

**operations**
```sql
uuid          UUID PRIMARY KEY          -- client-supplied idempotency key
status        VARCHAR NOT NULL          -- SUCCESS | FAILED
operation_type VARCHAR NOT NULL         -- RESERVE | RELEASE
room_type_id  VARCHAR REFERENCES room_types(room_type_id)
check_in      DATE NOT NULL
check_out     DATE NOT NULL
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
```

### Seed Data
- `data/room_types_data.sql` — inserts 12 room types with capacities, prices, and stock.
- `data/test_inventory_daily_data.sql` — sample reservations for 2025-12-05…2025-12-20 (useful for manual availability checks).

---

## HTTP API

Base path: `/rooms`

Common errors:
- `400 BAD REQUEST` — price range or date range provided partially.
- `404 NOT FOUND` — room type not found.
- `409 CONFLICT` — reservation/release failed (no inventory or idempotent repeat of a failed op).

### List All Room Types
`GET /rooms`

Response: `[{room_type_id, name, capacity_adults, price, total_quantity}]`

### Get Room Type by ID
`GET /rooms/{room_type_id}`

Response: same as above; `404` if missing.

### Search Availability
`GET /rooms/search`

Query params (all optional unless noted):
- `room_type_id` — exact match.
- `name` — exact match (e.g., `deluxe`, `econom`).
- `adults` — minimum capacity filter.
- `min_price` + `max_price` — must be provided together.
- `check_in` + `check_out` — must be provided together (date strings).

Behavior:
- Without `check_in`/`check_out`: returns filtered room types (no `available_quantity` calculation).
- With dates: builds date range `[check_in, check_out)`; rows with `available_quantity > 0` only.
  - Availability = `total_quantity - max(reserved_quantity)` over the range.
  - Missing `inventory_daily` rows are auto-created with `reserved_quantity=0` on first reservation, not during search.

Example:
```bash
curl "http://localhost:8000/rooms/search?adults=3&min_price=8000&max_price=15000&check_in=2025-12-10&check_out=2025-12-12"
```

### Reserve Rooms
`POST /rooms/reserve`

Body:
```json
{
  "uuid": "4f5c44e9-5082-4bfb-8eab-9d9ce57d3e71",
  "room_type_id": "STANDART_A",
  "check_in": "2025-12-10",
  "check_out": "2025-12-12"
}
```

Rules:
- Idempotent: repeating the same `uuid` returns success if already completed.
- On first call, creates missing `inventory_daily` rows for each date in the inclusive loop `[check_in, check_out]`; reservation updates rows for `[check_in, check_out)` (checkout date excluded from the increment).
- Locks selected rows (`FOR UPDATE`) when computing availability.
- Success: increments `reserved_quantity` by 1 per night and records `operations` with `status=SUCCESS`.
- Failure (no availability): writes `operations` with `status=FAILED` and returns `409`.

### Release Reservation
`POST /rooms/release`

Body is identical to `/rooms/reserve` (same UUID semantics).

Rules:
- If min reserved quantity in `[check_in, check_out)` is > 0, decrements `reserved_quantity` by 1 and records `operations` as `SUCCESS`.
- If nothing to release, writes/keeps `status=FAILED` and returns `409`.
- Replaying a successful UUID returns success without changes.

---

## Key Design Patterns

1. **Async SQLAlchemy Core** — explicit queries and CTEs, no ORM session-bound models in handlers.
2. **Idempotency via `operations`** — client-provided UUID prevents duplicate reservation/release effects.
3. **Pessimistic locking on reserve** — `WITH FOR UPDATE` guards concurrent reservations on the same range.
4. **Validation at schema level** — Pydantic `root_validator` enforces paired price/date filters.
5. **Simple layered split** — routers → DAO → database models keep HTTP details away from SQL code.

---

## Testing

Automated tests are not completed yet. You can validate changes manually:
- Use `uvicorn` + `curl`/`httpie` or FastAPI docs UI at `http://localhost:8000/docs`.
- Seed `data/test_inventory_daily_data.sql` to simulate partially booked periods.

---

## Database Management

### Migrations

```bash
# Apply latest
alembic upgrade head

# Downgrade one step
alembic downgrade -1

# Generate new migration (edit models first)
alembic revision --autogenerate -m "my change"
```

Alembic config: `alembic.ini`, env config in `app/migrations/env.py` (reads `.env` for DB params).

### Direct SQL Access

```bash
psql "postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"

-- Check room types
SELECT * FROM room_types;

-- Inspect availability for a range
SELECT * FROM inventory_daily WHERE room_type_id='STANDART_A' ORDER BY date LIMIT 10;

-- Review operation history
SELECT uuid, status, operation_type, check_in, check_out FROM operations ORDER BY created_at DESC LIMIT 20;
```

---

## Configuration

Environment variables (loaded via `app.config.Settings`):

| Variable | Example | Description |
|----------|---------|-------------|
| `DB_HOST` | e.g. `localhost` | PostgreSQL host |
| `DB_PORT` | e.g. `5432` | PostgreSQL port |
| `DB_USER` | e.g. `postgres` | User |
| `DB_PASS` | (set privately) | Password |
| `DB_NAME` | e.g. `inventory_app` | Database name |

Derived: `DATABASE_URL` is built automatically for asyncpg (`postgresql+asyncpg://...`).

---

## Production Considerations

1. Add authentication/authorization around reservation endpoints.
2. Add structured logging, metrics, and tracing (currently absent).
3. Improve validation: ensure `check_in < check_out`.
4. Add integration/unit tests around concurrency and edge cases.

---

## Development Workflow

```bash
# 1. Activate venv and install deps
# 2. Modify code / models / migrations
# 3. Run alembic upgrade head against dev DB
# 4. Start dev server: uvicorn app.main:app --reload
# 5. Exercise endpoints via /docs or curl
```

---

## Troubleshooting

- **400 price/date validation**: provide both `min_price`+`max_price` or both `check_in`+`check_out`.
- **404 room type**: verify `room_type_id` exists in `room_types`.
- **409 on reserve**: no availability for the requested range; inspect `inventory_daily` and ensure UUID not reused for a failed attempt unless intended.
- **Migrations fail**: confirm `.env` values and DB is reachable; check `alembic.ini` path `app/migrations`.
- **Compose DB not ready**: rerun `docker compose up` and ensure `inventory_db` is healthy.

---


## References

- API router: `app/rooms/router.py`
- Data access logic: `app/rooms/repository.py`
- Models: `app/rooms/models.py`
- Migrations: `app/migrations/`
- Seed data: `data/room_types_data.sql`, `data/test_inventory_daily_data.sql`

