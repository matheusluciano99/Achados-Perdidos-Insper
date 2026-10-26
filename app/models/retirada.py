from pydantic import ConfigDict, NaiveDatetime
from sqlmodel import Field, SQLModel


class RetiradaBase(SQLModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        title="Dados da retirada",
    )

    id_item: int = Field(
        gt=0,
        foreign_key="item.id",
        ondelete="RESTRICT",
        unique=True,
        description="Identificador do item retirado. Cada item admite uma única retirada.",
        schema_extra={"examples": [1]},
    )
    retirado_em: NaiveDatetime = Field(
        title="Data e hora da retirada",
        description="Data e hora da retirada, no horário de São Paulo, sem indicação de fuso.",
        schema_extra={"examples": ["2026-10-25T14:00:00"]},
    )


class Retirada(RetiradaBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    id_usuario: int = Field(foreign_key="usuario.id", ondelete="RESTRICT")


class RetiradaPublica(RetiradaBase):
    model_config = ConfigDict(title="Retirada")

    id: int = Field(description="Identificador da retirada, gerado pelo banco.")
    id_usuario: int = Field(description="Identificador do usuário que retirou o item.")
