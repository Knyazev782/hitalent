from datetime import datetime
from typing import Optional, Self

from pydantic import Field, model_validator

from app.schemas.base import Base
from app.schemas.employee import EmployeeRead
from app.schemas.constants import NAME_MAX_LENGTH, NAME_MIN_LENGTH


class DepartmentBase(Base):
    @model_validator(mode="after")
    def trim_name(self) -> Self:
        if self.name is not None:
            self.name = self.name.strip()
        return self


class DepartmentCreate(DepartmentBase):
    name: str = Field(..., min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    parent_id: Optional[int] = None


class DepartmentUpdate(DepartmentBase):
    name: Optional[str] = Field(None, min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    parent_id: Optional[int] = None


class DepartmentRead(Base):
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime


class DepartmentDetail(Base):
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime
    employees: list[EmployeeRead] = Field(default_factory=list)
    children: list["DepartmentDetail"] = Field(default_factory=list)


DepartmentDetail.model_rebuild()
