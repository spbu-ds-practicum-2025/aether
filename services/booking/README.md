# Booking Service Documentation

Distributed hotel booking service: create holds, confirm bookings, and manage notifications via RabbitMQ (Transactional Outbox).

## Quick Start

### Prerequisites

* Python 3.12+
* PostgreSQL 15+ (порт 5433 для изоляции от Inventory)
* RabbitMQ 3.12+
* Docker

### Run the Service Locally

```bash
# 1. Install dependencies
cd services/booking
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

```env
# 2. Configure environment
# Создайте файл .env в папке services/booking/
DB_HOST=localhost
DB_PORT=5433
DB_USER=postgres
DB_PASS=postgres
DB_NAME=booking_db
INVENTORY_SERVICE_URL=http://127.0.0.1:9000
RABBIT_HOST=localhost
RABBIT_PORT=5672
```

```bash
# 3. Run migrations
alembic upgrade head
```

```bash
# 4. Start the API (dev)
export PYTHONPATH="."            # Windows PowerShell: $env:PYTHONPATH="."
uvicorn app.main:app --reload --port 8001
```

### Run Publisher (Outbox Worker)

Чтобы события из БД попадали в RabbitMQ, необходимо запустить воркер:

```bash
export PYTHONPATH="."            # Windows PowerShell: $env:PYTHONPATH="."
python app/bookings/publisher.py
```

## Architecture

### Layers

```
[ FastAPI (app.main, app.bookings.router) ]
        ↓
[ BookingRepository (app.bookings.repository) ]
        ↓
[ Async engine + Transactional Outbox (app.database) ]
        ↓
[ PostgreSQL + RabbitMQ (via Publisher) ]
```

### Key Components

* **Transactional Outbox**: Гарантирует доставку событий в RabbitMQ только при успешном завершении транзакции в БД.
* **Inventory Integration**: Синхронные HTTP-вызовы к Inventory Service (`/reserve`, `/release`) для управления инвентарем.
* **TTL Management**: Автоматическая отмена просроченных "холдов" (по умолчанию 15 минут).

## Database Schema

### Tables

#### `bookings`

* `id`: SERIAL PRIMARY KEY
* `inventory_op_uuid`: UUID (ключ идемпотентности для Inventory)
* `status`: VARCHAR (`HOLD`, `CONFIRMED`, `CANCELLED`)
* `room_type_id`: VARCHAR
* `check_in` / `check_out`: DATE
* `ttl_expires_at`: TIMESTAMPTZ

#### `outbox_events`

* `id`: SERIAL PRIMARY KEY
* `event_type`: VARCHAR (e.g., `booking_confirmed`)
* `payload`: JSONB (данные события)
* `processed`: BOOLEAN (статус отправки в брокер)

## HTTP API

**Base path:** `/api/v1`

* `POST /holds/` — Создать временную бронь (статус `HOLD`).
* `POST /holds/{id}/confirm` — Подтвердить бронирование (статус `CONFIRMED`).
* `POST /holds/{id}/cancel` — Отменить бронь и освободить ресурсы.

## Event-Driven Integration

Сервис публикует сообщения в очередь `booking_notifications` при подтверждении.

* **Queue:** `booking_notifications`

**Payload Example:**

```json
{
  "event_type": "booking_confirmed",
  "payload": {
    "booking_id": "...",
    "inventory_uuid": "...",
    "room_type_id": "STANDART_A"
  }
}
```

## Troubleshooting

* **ValueError: invalid literal for int():** Проверьте корректность `DB_PORT` в `.env`.
* **Connection Refused (Port 9000):** Убедитесь, что Inventory Service запущен и доступен.
* **Events not in RabbitMQ:** Проверьте работу скрипта `publisher.py`.
