from datetime import date, datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import Base
from app.schemas.constants import NAME_MAX_LENGTH, NAME_MIN_LENGTH


class EmployeeRead(Base):
    id: int
    department_id: int
    full_name: str
    position: str
    hired_at: Optional[date]
    created_at: datetime


class EmployeeCreate(Base):
    full_name: str = Field(..., min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    position: str = Field(..., min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    hired_at: Optional[date] = None
