from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    DepartmentCreate,
    DepartmentDetail,
    DepartmentRead,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeRead,
)
from app.services import (
    create_department,
    create_employee,
    delete_department,
    get_department_detail,
    update_department,
)
from app.schemas.constants import DEPTH_DEFAULT, DEPTH_MAX, DEPTH_MIN
from app.services.constants import DeleteMode

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("/", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def api_create_department(data: DepartmentCreate, db: AsyncSession = Depends(get_db)):
    return await create_department(db, data)


@router.post("/{department_id}/employees/", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def api_create_employee(
    department_id: int, data: EmployeeCreate, db: AsyncSession = Depends(get_db)
):
    return await create_employee(db, department_id, data)


@router.get("/{department_id}", response_model=DepartmentDetail)
async def api_get_department(
    department_id: int,
    depth: int = Query(DEPTH_DEFAULT, ge=DEPTH_MIN, le=DEPTH_MAX),
    include_employees: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    return await get_department_detail(db, department_id, depth, include_employees)


@router.patch("/{department_id}", response_model=DepartmentRead)
async def api_update_department(
    department_id: int, data: DepartmentUpdate, db: AsyncSession = Depends(get_db)
):
    return await update_department(db, department_id, data)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_department(
    department_id: int,
    mode: DeleteMode = Query(DeleteMode.CASCADE),
    reassign_to_department_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_department(db, department_id, mode, reassign_to_department_id)
