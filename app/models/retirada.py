from pydantic import ConfigDict, EmailStr, NaiveDatetime
from sqlalchemy import String
from sqlmodel import Field, SQLModel


class RetiradaBase(SQLModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_by_name=True,
        title="Dados da retirada",
    )

    item_id: int = Field(
        alias="id_item",
        gt=0,
        foreign_key="item.id",
        ondelete="RESTRICT",
        unique=True,
        description="Identificador do item retirado. Cada item admite uma única retirada.",
        schema_extra={"examples": [1]},
    )
    collector_name: str = Field(
        alias="nome_retirante",
        title="Nome de quem retirou",
        min_length=1,
        max_length=100,
        description="Nome da pessoa que retirou o item.",
        schema_extra={"examples": ["Maria Silva"]},
    )
    collector_email: EmailStr = Field(
        alias="email_retirante",
        title="E-mail de quem retirou",
        max_length=254,
        sa_type=String(254),
        description="E-mail da pessoa que retirou o item.",
        schema_extra={"examples": ["maria.silva@al.insper.edu.br"]},
    )
    collected_at: NaiveDatetime = Field(
        alias="retirado_em",
        title="Data e hora da retirada",
        description="Data e hora da retirada, no horário de São Paulo, sem indicação de fuso.",
        schema_extra={"examples": ["2026-10-25T14:00:00"]},
    )


class Retirada(RetiradaBase, table=True):
    __tablename__ = "collection"

    id: int | None = Field(default=None, primary_key=True)


class RetiradaPublica(RetiradaBase):
    model_config = ConfigDict(title="Retirada")

    id: int = Field(description="Identificador da retirada, gerado pelo banco.")
