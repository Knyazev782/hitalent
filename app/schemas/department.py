from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.employee import EmployeeRead


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parent_id: Optional[int] = None

    @model_validator(mode="after")
    def trim_name(self) -> "DepartmentCreate":
        self.name = self.name.strip()
        return self


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    parent_id: Optional[int] = None

    @model_validator(mode="after")
    def trim_name(self) -> "DepartmentUpdate":
        if self.name is not None:
            self.name = self.name.strip()
        return self


class DepartmentRead(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class DepartmentDetail(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime
    employees: list[EmployeeRead] = []
    children: list["DepartmentDetail"] = []

    model_config = {"from_attributes": True}


DepartmentDetail.model_rebuild()
