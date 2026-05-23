from enum import StrEnum

ROOT_PARENT_ID = 0

AUTO_CREATE_TABLES_ENV = "AUTO_CREATE_TABLES"

DEPARTMENT_NOT_FOUND = "Подразделение не найдено"
PARENT_NOT_FOUND = "Родительское подразделение не найдено"
NEW_PARENT_NOT_FOUND = "Новое родительское подразделение не найдено"
TARGET_DEPARTMENT_NOT_FOUND = "Целевое подразделение для переноса не найдено"
SELF_PARENT = "Подразделение не может быть родителем самого себя"
CYCLE_DETECTED = "Нельзя переместить подразделение в собственное поддерево (обнаружен цикл)"
REASSIGN_REQUIRED = "При режиме reassign необходимо указать reassign_to_department_id"
REASSIGN_INSIDE_SUBTREE = "Целевое подразделение для переноса находится внутри удаляемого поддерева"
REASSIGN_TO_SELF = "Нельзя перенести сотрудников в удаляемое подразделение"


class DeleteMode(StrEnum):
    CASCADE = "cascade"
    REASSIGN = "reassign"


def duplicate_name_msg(name: str) -> str:
    return f"Подразделение с именем '{name}' уже существует в данном родителе"
