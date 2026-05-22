from typing import Any

from fastapi.testclient import TestClient


def _create_department(client: TestClient, name: str, parent_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/departments/", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_department_and_get_with_tree(client: TestClient) -> None:
    """Создание подразделения, получение с деревом и сотрудниками."""
    dept = _create_department(client, "  IT отдел  ")

    assert dept["name"] == "IT отдел"
    assert dept["parent_id"] is None

    child = _create_department(client, "Backend", dept["id"])
    client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "Иван Иванов", "position": "Разработчик", "hired_at": "2024-01-15"},
    )

    detail = client.get(f"/departments/{dept['id']}").json()
    assert len(detail["employees"]) == 1
    assert detail["employees"][0]["full_name"] == "Иван Иванов"
    assert len(detail["children"]) == 1
    assert detail["children"][0]["name"] == "Backend"

    detail_no_emp = client.get(f"/departments/{dept['id']}", params={"include_employees": False}).json()
    assert detail_no_emp["employees"] == []

    detail_d0 = client.get(f"/departments/{dept['id']}", params={"depth": 0}).json()
    assert detail_d0["children"] == []


def test_unique_name_within_same_parent(client: TestClient) -> None:
    """Два подразделения с одинаковым именем в одном родителе — 409."""
    parent = _create_department(client, "IT")
    _create_department(client, "Backend", parent["id"])

    response = client.post(
        "/departments/", json={"name": "Backend", "parent_id": parent["id"]}
    )
    assert response.status_code == 409


def test_same_name_in_different_parents_ok(client: TestClient) -> None:
    """Одинаковое имя в разных родителях — допустимо."""
    p1 = _create_department(client, "IT")
    p2 = _create_department(client, "HR")
    r1 = _create_department(client, "Backend", p1["id"])
    r2 = _create_department(client, "Backend", p2["id"])
    assert r1["id"] != r2["id"]


def test_department_404_on_nonexistent(client: TestClient) -> None:
    """GET/PATCH/DELETE несуществующего подразделения — 404."""
    assert client.get("/departments/9999").status_code == 404
    assert client.patch("/departments/9999", json={"name": "X"}).status_code == 404
    assert client.delete("/departments/9999", params={"mode": "cascade"}).status_code == 404


def test_update_department_rename_and_move(client: TestClient) -> None:
    """Переименование и перемещение подразделения."""
    root = _create_department(client, "Корень")
    child = _create_department(client, "Старое имя", root["id"])
    new_root = _create_department(client, "Новый корень")

    renamed = client.patch(f"/departments/{child['id']}", json={"name": "Новое имя"}).json()
    assert renamed["name"] == "Новое имя"

    moved = client.patch(f"/departments/{child['id']}", json={"parent_id": new_root["id"]}).json()
    assert moved["parent_id"] == new_root["id"]


def test_move_to_parent_with_same_name_409(client: TestClient) -> None:
    """Перемещение в родителя, где уже есть подразделение с таким именем — 409."""
    p1 = _create_department(client, "IT")
    p2 = _create_department(client, "HR")
    _create_department(client, "Backend", p1["id"])
    b2 = _create_department(client, "Backend", p2["id"])

    response = client.patch(f"/departments/{b2['id']}", json={"parent_id": p1["id"]})
    assert response.status_code == 409


def test_cycle_detection_self_reference(client: TestClient) -> None:
    """Подразделение не может стать родителем самого себя — 400."""
    dept = _create_department(client, "IT")
    response = client.patch(f"/departments/{dept['id']}", json={"parent_id": dept["id"]})
    assert response.status_code == 400


def test_cycle_detection_subtree(client: TestClient) -> None:
    """Нельзя переместить родителя в собственное поддерево — 409."""
    root = _create_department(client, "Корень")
    child = _create_department(client, "Ребёнок", root["id"])
    response = client.patch(f"/departments/{root['id']}", json={"parent_id": child["id"]})
    assert response.status_code == 409


def test_cascade_delete_removes_children_and_employees(client: TestClient) -> None:
    """Каскадное удаление: удаляется подразделение, дети и сотрудники."""
    parent = _create_department(client, "Корень")
    child = _create_department(client, "Дочерний", parent["id"])
    client.post(
        f"/departments/{parent['id']}/employees/",
        json={"full_name": "Иван", "position": "Разработчик"},
    )
    client.post(
        f"/departments/{child['id']}/employees/",
        json={"full_name": "Пётр", "position": "Тестировщик"},
    )

    response = client.delete(f"/departments/{parent['id']}", params={"mode": "cascade"})
    assert response.status_code == 204
    assert client.get(f"/departments/{parent['id']}").status_code == 404
    assert client.get(f"/departments/{child['id']}").status_code == 404


def test_reassign_delete_moves_employees(client: TestClient) -> None:
    """Удаление с reassign: сотрудники переносятся в целевое подразделение."""
    old_dept = _create_department(client, "Старый отдел")
    new_dept = _create_department(client, "Новый отдел")
    client.post(
        f"/departments/{old_dept['id']}/employees/",
        json={"full_name": "Иван", "position": "Разработчик"},
    )

    response = client.delete(
        f"/departments/{old_dept['id']}",
        params={"mode": "reassign", "reassign_to_department_id": new_dept["id"]},
    )
    assert response.status_code == 204
    assert client.get(f"/departments/{old_dept['id']}").status_code == 404

    new_detail = client.get(f"/departments/{new_dept['id']}").json()
    assert len(new_detail["employees"]) == 1
    assert new_detail["employees"][0]["full_name"] == "Иван"


def test_reassign_errors(client: TestClient) -> None:
    """Ошибки при reassign: без цели, в себя и в дочернее подразделение."""
    dept = _create_department(client, "Отдел")

    assert client.delete(f"/departments/{dept['id']}", params={"mode": "reassign"}).status_code == 400

    assert client.delete(
        f"/departments/{dept['id']}",
        params={"mode": "reassign", "reassign_to_department_id": dept["id"]},
    ).status_code == 400

    root = _create_department(client, "Корень")
    child = _create_department(client, "Дочерний", root["id"])
    assert client.delete(
        f"/departments/{root['id']}",
        params={"mode": "reassign", "reassign_to_department_id": child["id"]},
    ).status_code == 400


def test_create_employee_validation(client: TestClient) -> None:
    """Создание сотрудника: валидные и невалидные данные."""
    dept = _create_department(client, "IT")

    emp = client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "Иван Иванов", "position": "Разработчик", "hired_at": "2024-01-15"},
    ).json()
    assert emp["full_name"] == "Иван Иванов"
    assert emp["hired_at"] == "2024-01-15"

    emp2 = client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "Пётр Петров", "position": "Тестировщик"},
    ).json()
    assert emp2["hired_at"] is None

    assert client.post(
        f"/departments/{dept['id']}/employees/",
        json={"full_name": "", "position": "Dev"},
    ).status_code == 422

    assert client.post(
        "/departments/9999/employees/",
        json={"full_name": "Иван", "position": "Dev"},
    ).status_code == 404


def test_validation_empty_and_long_name(client: TestClient) -> None:
    """Пустое и слишком длинное имя подразделения — 422."""
    assert client.post("/departments/", json={"name": ""}).status_code == 422
    assert client.post("/departments/", json={"name": "x" * 201}).status_code == 422
