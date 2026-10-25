from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlmodel import create_engine


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mysql_host: str = Field(default="127.0.0.1", min_length=1)
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    mysql_database: str = Field(min_length=1)
    mysql_user: str = Field(min_length=1)
    mysql_password: SecretStr = Field(min_length=1)


settings = DatabaseSettings()

engine = create_engine(
    URL.create(
        "mysql+pymysql",
        username=settings.mysql_user,
        password=settings.mysql_password.get_secret_value(),
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        query={"charset": "utf8mb4"},
    ),
    pool_pre_ping=True,
)
