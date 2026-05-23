import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import Base, engine
from app.models import Department, Employee  # noqa: F401
from app.routers.departments import router as departments_router
from app.services.constants import AUTO_CREATE_TABLES_ENV

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESET_SEQUENCES_SQL = (
    "SELECT setval(pg_get_serial_sequence('departments', 'id'), 1, false), "
    "setval(pg_get_serial_sequence('employees', 'id'), 1, false)"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv(AUTO_CREATE_TABLES_ENV, "1") == "1":
        logger.info("Создание таблиц в базе данных...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if engine.dialect.name == "postgresql":
                await conn.execute(text(RESET_SEQUENCES_SQL))
    logger.info("Приложение запущено")
    yield
    logger.info("Приложение останавливается")


app = FastAPI(
    title="API организационной структуры",
    description="API для управления подразделениями и сотрудниками",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(departments_router)
