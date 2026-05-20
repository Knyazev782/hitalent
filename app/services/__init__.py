from collections import deque
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Department, Employee
from app.schemas import DepartmentCreate, DepartmentUpdate, EmployeeCreate


def _collect_subtree_ids(db: Session, department_id: int) -> set[int]:
    """Собирает все ID подразделений в поддереве, включая корень."""
    ids: set[int] = {department_id}
    queue: deque[int] = deque([department_id])
    while queue:
        current: int = queue.popleft()
        children = list(db.execute(
            select(Department.id).where(Department.parent_id == current)
        ).scalars().all())
        for child_id in children:
            if child_id not in ids:
                ids.add(child_id)
                queue.append(child_id)
    return ids


def create_department(db: Session, data: DepartmentCreate) -> Department:
    if data.parent_id is not None and data.parent_id != 0:
        parent: Optional[Department] = db.get(Department, data.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Родительское подразделение не найдено")
    else:
        data.parent_id = None

    existing: Optional[Department] = db.execute(
        select(Department).where(
            Department.name == data.name,
            Department.parent_id == data.parent_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Подразделение с именем '{data.name}' уже существует в данном родителе",
        )

    department: Department = Department(name=data.name, parent_id=data.parent_id)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def create_employee(db: Session, department_id: int, data: EmployeeCreate) -> Employee:
    department: Optional[Department] = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")

    employee: Employee = Employee(
        department_id=department_id,
        full_name=data.full_name,
        position=data.position,
        hired_at=data.hired_at,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def _build_department_tree(
    db: Session,
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
        employees = list(db.execute(
            select(Employee)
            .where(Employee.department_id == department.id)
            .order_by(Employee.created_at, Employee.full_name)
        ).scalars().all())
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
        children = list(db.execute(
            select(Department).where(Department.parent_id == department.id)
        ).scalars().all())
        result["children"] = [
            _build_department_tree(db, child, depth - 1, include_employees)
            for child in children
        ]

    return result


def get_department_detail(
    db: Session,
    department_id: int,
    depth: int = 1,
    include_employees: bool = True,
) -> dict:
    department: Optional[Department] = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")

    return _build_department_tree(db, department, depth, include_employees)


def update_department(db: Session, department_id: int, data: DepartmentUpdate) -> Department:
    department: Optional[Department] = db.get(Department, department_id)
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

        new_parent: Optional[Department] = db.get(Department, data.parent_id)
        if new_parent is None:
            raise HTTPException(
                status_code=404, detail="Новое родительское подразделение не найдено"
            )

        subtree_ids: set[int] = _collect_subtree_ids(db, department_id)
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

    # Проверка уникальности имени при любом изменении name или parent_id
    if data.name is not None or parent_changed:
        existing: Optional[Department] = db.execute(
            select(Department).where(
                Department.name == department.name,
                Department.parent_id == department.parent_id,
                Department.id != department_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Подразделение с именем '{department.name}' уже существует в данном родителе",
            )

    db.commit()
    db.refresh(department)
    return department


def delete_department(
    db: Session,
    department_id: int,
    mode: str,
    reassign_to_department_id: Optional[int] = None,
) -> None:
    department: Optional[Department] = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")

    subtree_ids: set[int] = _collect_subtree_ids(db, department_id)

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
        target: Optional[Department] = db.get(Department, reassign_to_department_id)
        if target is None:
            raise HTTPException(
                status_code=404, detail="Целевое подразделение для переноса не найдено"
            )
        if reassign_to_department_id == department_id:
            raise HTTPException(
                status_code=400,
                detail="Нельзя перенести сотрудников в удаляемое подразделение",
            )

        db.execute(
            update(Employee)
            .where(Employee.department_id.in_(subtree_ids))
            .values(department_id=reassign_to_department_id)
        )
        db.flush()

    db.execute(
        delete(Employee).where(Employee.department_id.in_(subtree_ids))
    )
    db.execute(
        delete(Department).where(Department.id.in_(subtree_ids))
    )
    db.commit()
