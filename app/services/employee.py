from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department, Employee
from app.schemas import EmployeeCreate
from app.services.constants import DEPARTMENT_NOT_FOUND


async def create_employee(db: AsyncSession, department_id: int, data: EmployeeCreate) -> Employee:
    department: Optional[Department] = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DEPARTMENT_NOT_FOUND)

    employee: Employee = Employee(
        department_id=department_id,
        full_name=data.full_name,
        position=data.position,
        hired_at=data.hired_at,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee
