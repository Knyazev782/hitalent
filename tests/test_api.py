from typing import Any

import pytest
from httpx import AsyncClient


async def _create_department(client: AsyncClient, name: str, parent_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = await client.post("/departments/", json=payload)
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_create_department_and_get_with_tree(client: AsyncClient) -> None:
    """Создание подразделения, получение с деревом и сотрудниками."""
    dept = await _create_department(client, "  IT отдел  ")

    assert dept["name"] == "IT отдел"
    assert dept["parent_id"] is None

    child = await _create_department(client, "Backend", dept["id"])
    await client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "Иван Иванов", "position": "Разработчик", "hired_at": "2024-01-15"},
    )

    detail = (await client.get(f"/departments/{dept['id']}")).json()
    assert len(detail["employees"]) == 1
    assert detail["employees"][0]["full_name"] == "Иван Иванов"
    assert len(detail["children"]) == 1
    assert detail["children"][0]["name"] == "Backend"

    detail_no_emp = (await client.get(f"/departments/{dept['id']}", params={"include_employees": False})).json()
    assert detail_no_emp["employees"] == []

    detail_d0 = (await client.get(f"/departments/{dept['id']}", params={"depth": 0})).json()
    assert detail_d0["children"] == []


@pytest.mark.asyncio
async def test_unique_name_within_same_parent(client: AsyncClient) -> None:
    """Два подразделения с одинаковым именем в одном родителе — 409."""
    parent = await _create_department(client, "IT")
    await _create_department(client, "Backend", parent["id"])

    response = await client.post(
        "/departments/", json={"name": "Backend", "parent_id": parent["id"]}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_same_name_in_different_parents_ok(client: AsyncClient) -> None:
    """Одинаковое имя в разных родителях — допустимо."""
    p1 = await _create_department(client, "IT")
    p2 = await _create_department(client, "HR")
    r1 = await _create_department(client, "Backend", p1["id"])
    r2 = await _create_department(client, "Backend", p2["id"])
    assert r1["id"] != r2["id"]


@pytest.mark.asyncio
async def test_department_404_on_nonexistent(client: AsyncClient) -> None:
    """GET/PATCH/DELETE несуществующего подразделения — 404."""
    assert (await client.get("/departments/9999")).status_code == 404
    assert (await client.patch("/departments/9999", json={"name": "X"})).status_code == 404
    assert (await client.delete("/departments/9999", params={"mode": "cascade"})).status_code == 404


@pytest.mark.asyncio
async def test_update_department_rename_and_move(client: AsyncClient) -> None:
    """Переименование и перемещение подразделения."""
    root = await _create_department(client, "Корень")
    child = await _create_department(client, "Старое имя", root["id"])
    new_root = await _create_department(client, "Новый корень")

    renamed = (await client.patch(f"/departments/{child['id']}", json={"name": "Новое имя"})).json()
    assert renamed["name"] == "Новое имя"

    moved = (await client.patch(f"/departments/{child['id']}", json={"parent_id": new_root["id"]})).json()
    assert moved["parent_id"] == new_root["id"]


@pytest.mark.asyncio
async def test_move_to_parent_with_same_name_409(client: AsyncClient) -> None:
    """Перемещение в родителя, где уже есть подразделение с таким именем — 409."""
    p1 = await _create_department(client, "IT")
    p2 = await _create_department(client, "HR")
    await _create_department(client, "Backend", p1["id"])
    b2 = await _create_department(client, "Backend", p2["id"])

    response = await client.patch(f"/departments/{b2['id']}", json={"parent_id": p1["id"]})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cycle_detection_self_reference(client: AsyncClient) -> None:
    """Подразделение не может стать родителем самого себя — 400."""
    dept = await _create_department(client, "IT")
    response = await client.patch(f"/departments/{dept['id']}", json={"parent_id": dept["id"]})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cycle_detection_subtree(client: AsyncClient) -> None:
    """Нельзя переместить родителя в собственное поддерево — 409."""
    root = await _create_department(client, "Корень")
    child = await _create_department(client, "Ребёнок", root["id"])
    response = await client.patch(f"/departments/{root['id']}", json={"parent_id": child["id"]})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cascade_delete_removes_children_and_employees(client: AsyncClient) -> None:
    """Каскадное удаление: удаляется подразделение, дети и сотрудники."""
    parent = await _create_department(client, "Корень")
    child = await _create_department(client, "Дочерний", parent["id"])
    await client.post(
        f"/departments/{parent['id']}/employees/",
        json={"full_name": "Иван", "position": "Разработчик"},
    )
    await client.post(
        f"/departments/{child['id']}/employees/",
        json={"full_name": "Пётр", "position": "Тестировщик"},
    )

    response = await client.delete(f"/departments/{parent['id']}", params={"mode": "cascade"})
    assert response.status_code == 204
    assert (await client.get(f"/departments/{parent['id']}")).status_code == 404
    assert (await client.get(f"/departments/{child['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_reassign_delete_moves_employees(client: AsyncClient) -> None:
    """Удаление с reassign: сотрудники переносятся в целевое подразделение."""
    old_dept = await _create_department(client, "Старый отдел")
    new_dept = await _create_department(client, "Новый отдел")
    await client.post(
        f"/departments/{old_dept['id']}/employees/",
        json={"full_name": "Иван", "position": "Разработчик"},
    )

    response = await client.delete(
        f"/departments/{old_dept['id']}",
        params={"mode": "reassign", "reassign_to_department_id": new_dept["id"]},
    )
    assert response.status_code == 204
    assert (await client.get(f"/departments/{old_dept['id']}")).status_code == 404

    new_detail = (await client.get(f"/departments/{new_dept['id']}")).json()
    assert len(new_detail["employees"]) == 1
    assert new_detail["employees"][0]["full_name"] == "Иван"


@pytest.mark.asyncio
async def test_reassign_errors(client: AsyncClient) -> None:
    """Ошибки при reassign: без цели, в себя и в дочернее подразделение."""
    dept = await _create_department(client, "Отдел")

    assert (await client.delete(f"/departments/{dept['id']}", params={"mode": "reassign"})).status_code == 400

    assert (await client.delete(
        f"/departments/{dept['id']}",
        params={"mode": "reassign", "reassign_to_department_id": dept["id"]},
    )).status_code == 400

    root = await _create_department(client, "Корень")
    child = await _create_department(client, "Дочерний", root["id"])
    assert (await client.delete(
        f"/departments/{root['id']}",
        params={"mode": "reassign", "reassign_to_department_id": child["id"]},
    )).status_code == 400


@pytest.mark.asyncio
async def test_create_employee_validation(client: AsyncClient) -> None:
    """Создание сотрудника: валидные и невалидные данные."""
    dept = await _create_department(client, "IT")

    emp = (await client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "Иван Иванов", "position": "Разработчик", "hired_at": "2024-01-15"},
    )).json()
    assert emp["full_name"] == "Иван Иванов"
    assert emp["hired_at"] == "2024-01-15"

    emp2 = (await client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "Пётр Петров", "position": "Тестировщик"},
    )).json()
    assert emp2["hired_at"] is None

    assert (await client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "", "position": "Dev"},
    )).status_code == 422

    assert (await client.post(
        "/departments/9999/employees/",
        json={"full_name": "Иван", "position": "Dev"},
    )).status_code == 404


@pytest.mark.asyncio
async def test_validation_empty_and_long_name(client: AsyncClient) -> None:
    """Пустое и слишком длинное имя подразделения — 422."""
    assert (await client.post("/departments/", json={"name": ""})).status_code == 422
    assert (await client.post("/departments/", json={"name": "x" * 201})).status_code == 422
