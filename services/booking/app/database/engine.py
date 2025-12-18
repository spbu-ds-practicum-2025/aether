import os
from pathlib import Path # Добавь этот импорт
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base 
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

# Считываем конфигурацию
DB_HOST = os.getenv("DB_HOST") 

# Считываем конфигурацию DB из .env
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

# Формируем URL для asyncpg
# Обратите внимание: драйвер 'psycopg' должен быть установлен (pip install psycopg[binary])
DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 1. Создание асинхронного движка
engine = create_async_engine(
    DATABASE_URL,
    echo=False, # Установите True для отладки SQL-запросов
    pool_size=20,
    max_overflow=0,
)

# 2. Базовый класс для декларативных моделей SQLAlchemy
# Теперь импортирован корректно.
Base = declarative_base()

# 3. Асинхронный конструктор сессий
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# 4. Вспомогательная функция для получения сессии (для зависимостей FastAPI)
async def get_async_session():
    async with AsyncSessionLocal() as session:
        yield session