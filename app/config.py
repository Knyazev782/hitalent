from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/hitalent"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
