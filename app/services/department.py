from collections import deque
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department, Employee
from app.schemas import DepartmentCreate, DepartmentUpdate


async def _collect_subtree_ids(db: AsyncSession, department_id: int) -> set[int]:
    """Собирает все ID подразделений в поддереве, включая корень."""
    ids: set[int] = {department_id}
    queue: deque[int] = deque([department_id])
    while queue:
        current: int = queue.popleft()
        result = await db.execute(
            select(Department.id).where(Department.parent_id == current)
        )
        children = list(result.scalars().all())
        for child_id in children:
            if child_id not in ids:
                ids.add(child_id)
                queue.append(child_id)
    return ids


async def create_department(db: AsyncSession, data: DepartmentCreate) -> Department:
    if data.parent_id is not None and data.parent_id != 0:
        parent: Optional[Department] = await db.get(Department, data.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Родительское подразделение не найдено")
    else:
        data.parent_id = None

    result = await db.execute(
        select(Department).where(
            Department.name == data.name,
            Department.parent_id == data.parent_id,
        )
    )
    existing: Optional[Department] = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Подразделение с именем '{data.name}' уже существует в данном родителе",
        )

    department: Department = Department(name=data.name, parent_id=data.parent_id)
    db.add(department)
    await db.commit()
    await db.refresh(department)
    return department


async def update_department(db: AsyncSession, department_id: int, data: DepartmentUpdate) -> Department:
    department: Optional[Department] = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")

    if data.name is not None:
        department.name = data.name

    parent_changed: bool = False
    if data.parent_id is not None and data.parent_id != 0:
        if data.parent_id == department_id:
            raise HTTPException(
                status_code=400,
                detail="Подразделение не может быть родителем самого себя",
            )

        new_parent: Optional[Department] = await db.get(Department, data.parent_id)
        if new_parent is None:
            raise HTTPException(
                status_code=404, detail="Новое родительское подразделение не найдено"
            )

        subtree_ids: set[int] = await _collect_subtree_ids(db, department_id)
        if data.parent_id in subtree_ids:
            raise HTTPException(
                status_code=409,
                detail="Нельзя переместить подразделение в собственное поддерево (обнаружен цикл)",
            )

        department.parent_id = data.parent_id
        parent_changed = True
    elif data.parent_id is None or data.parent_id == 0:
        if "parent_id" in data.model_fields_set:
            department.parent_id = None
            parent_changed = True

    if data.name is not None or parent_changed:
        result = await db.execute(
            select(Department).where(
                Department.name == department.name,
                Department.parent_id == department.parent_id,
                Department.id != department_id,
            )
        )
        existing: Optional[Department] = result.scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Подразделение с именем '{department.name}' уже существует в данном родителе",
            )

    await db.commit()
    await db.refresh(department)
    return department


async def _build_department_tree(
    db: AsyncSession,
    department: Department,
    depth: int,
    include_employees: bool,
) -> dict:
    """Рекурсивно строит дерево подразделений до указанной глубины."""
    result: dict = {
        "id": department.id,
        "name": department.name,
        "parent_id": department.parent_id,
        "created_at": department.created_at,
        "employees": [],
        "children": [],
    }

    if include_employees:
        emp_result = await db.execute(
            select(Employee)
            .where(Employee.department_id == department.id)
            .order_by(Employee.created_at, Employee.full_name)
        )
        employees = list(emp_result.scalars().all())
        result["employees"] = [
            {
                "id": e.id,
                "department_id": e.department_id,
                "full_name": e.full_name,
                "position": e.position,
                "hired_at": e.hired_at,
                "created_at": e.created_at,
            }
            for e in employees
        ]

    if depth > 0:
        child_result = await db.execute(
            select(Department).where(Department.parent_id == department.id)
        )
        children = list(child_result.scalars().all())
        result["children"] = [
            await _build_department_tree(db, child, depth - 1, include_employees)
            for child in children
        ]

    return result


async def get_department_detail(
    db: AsyncSession,
    department_id: int,
    depth: int = 1,
    include_employees: bool = True,
) -> dict:
    department: Optional[Department] = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")

    return await _build_department_tree(db, department, depth, include_employees)


async def delete_department(
    db: AsyncSession,
    department_id: int,
    mode: str,
    reassign_to_department_id: Optional[int] = None,
) -> None:
    department: Optional[Department] = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")

    subtree_ids: set[int] = await _collect_subtree_ids(db, department_id)

    if mode == "reassign":
        if reassign_to_department_id is None:
            raise HTTPException(
                status_code=400,
                detail="При режиме reassign необходимо указать reassign_to_department_id",
            )
        if reassign_to_department_id in subtree_ids:
            raise HTTPException(
                status_code=400,
                detail="Целевое подразделение для переноса находится внутри удаляемого поддерева",
            )
        target: Optional[Department] = await db.get(Department, reassign_to_department_id)
        if target is None:
            raise HTTPException(
                status_code=404, detail="Целевое подразделение для переноса не найдено"
            )
        if reassign_to_department_id == department_id:
            raise HTTPException(
                status_code=400,
                detail="Нельзя перенести сотрудников в удаляемое подразделение",
            )

        await db.execute(
            update(Employee)
            .where(Employee.department_id.in_(subtree_ids))
            .values(department_id=reassign_to_department_id)
        )
        await db.flush()

    await db.execute(
        delete(Employee).where(Employee.department_id.in_(subtree_ids))
    )
    await db.execute(
        delete(Department).where(Department.id.in_(subtree_ids))
    )
    await db.commit()
