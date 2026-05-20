from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

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

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("/", response_model=DepartmentRead, status_code=201)
def api_create_department(data: DepartmentCreate, db: Session = Depends(get_db)):
    return create_department(db, data)


@router.post("/{department_id}/employees/", response_model=EmployeeRead, status_code=201)
def api_create_employee(
    department_id: int, data: EmployeeCreate, db: Session = Depends(get_db)
):
    return create_employee(db, department_id, data)


@router.get("/{department_id}", response_model=DepartmentDetail)
def api_get_department(
    department_id: int,
    depth: int = Query(1, ge=0, le=5),
    include_employees: bool = Query(True),
    db: Session = Depends(get_db),
):
    return get_department_detail(db, department_id, depth, include_employees)


@router.patch("/{department_id}", response_model=DepartmentRead)
def api_update_department(
    department_id: int, data: DepartmentUpdate, db: Session = Depends(get_db)
):
    return update_department(db, department_id, data)


@router.delete("/{department_id}", status_code=204)
def api_delete_department(
    department_id: int,
    mode: str = Query("cascade", pattern="^(cascade|reassign)$"),
    reassign_to_department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> None:
    delete_department(db, department_id, mode, reassign_to_department_id)
