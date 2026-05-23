import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base
from app.database import engine
from app.models import Department, Employee  # noqa: F401
from app.routers.departments import router as departments_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("AUTO_CREATE_TABLES", "1") == "1":

        logger.info("Создание таблиц в базе данных...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
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
