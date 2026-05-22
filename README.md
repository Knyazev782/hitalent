 # API организационной структуры

REST API для управления иерархической структурой подразделений и сотрудников.

## Стек

- **FastAPI** — веб-фреймворк
- **SQLAlchemy 2.0** — ORM
- **PostgreSQL 16** — база данных
- **Alembic** — миграции
- **Docker / Docker Compose** — контейнеризация

## Быстрый старт

```bash
git clone https://github.com/Knyazev782/hitalent
docker-compose up --build
```

API будет доступно на: http://localhost:8000

Документация (Swagger): http://localhost:8000/docs

## Эндпоинты

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/departments/` | Создать подразделение |
| `POST` | `/departments/{id}/employees/` | Создать сотрудника |
| `GET` | `/departments/{id}` | Получить подразделение (дерево + сотрудники) |
| `PATCH` | `/departments/{id}` | Обновить подразделение (имя / parent) |
| `DELETE` | `/departments/{id}` | Удалить подразделение (cascade / reassign) |

### Параметры GET /departments/{id}

- `depth` (int, 0-5, по умолчанию 1) — глубина вложенных подразделений
- `include_employees` (bool, по умолчанию true) — включать ли список сотрудников

### Параметры DELETE /departments/{id}

- `mode` — `cascade` (удалить всё) или `reassign` (перенести сотрудников)
- `reassign_to_department_id` — обязателен при mode=reassign

## Запуск тестов (локально)

```bash
pip install -r requirements.txt
pytest -v
```

## Структура проекта

```
app/
  main.py          # FastAPI application
  config.py        # Settings (pydantic-settings)
  database.py      # SQLAlchemy engine + session
  models/          # Department, Employee
  schemas/         # Pydantic schemas
  routers/         # API endpoints
  services/        # Business logic
migrations/        # Alembic migrations
tests/             # pytest tests
```
