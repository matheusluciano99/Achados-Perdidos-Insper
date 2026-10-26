from pydantic import ConfigDict, EmailStr, field_validator
from sqlalchemy import String
from sqlmodel import Field, SQLModel


class Usuario(SQLModel, table=True):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=254, unique=True, sa_type=String(254))

    @field_validator("email")
    @classmethod
    def validar_email_insper(cls, email: str) -> str:
        email = email.lower()
        if email.rsplit("@", 1)[1] not in {"al.insper.edu.br", "insper.edu.br"}:
            raise ValueError("Use um e-mail institucional do Insper.")
        return email
