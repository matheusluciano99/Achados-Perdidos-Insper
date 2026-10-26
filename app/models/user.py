from typing import Annotated

from pydantic import AfterValidator, ConfigDict, EmailStr
from sqlalchemy import String
from sqlmodel import Field, SQLModel


def validar_email_insper(email: str) -> str:
    email = email.lower()
    if email.rsplit("@", 1)[1] not in {"al.insper.edu.br", "insper.edu.br"}:
        raise ValueError("Use um e-mail institucional do Insper.")
    return email


EmailInsper = Annotated[EmailStr, AfterValidator(validar_email_insper)]


class Usuario(SQLModel, table=True):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(min_length=1, max_length=100)
    email: EmailInsper = Field(max_length=254, unique=True, sa_type=String(254))
