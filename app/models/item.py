from pydantic import ConfigDict, NaiveDatetime
from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_by_name=True,
        title="Dados do item",
    )

    name: str = Field(
        alias="nome",
        min_length=1,
        max_length=100,
        description="Nome do objeto encontrado.",
        schema_extra={"examples": ["Garrafa de água"]},
    )
    description: str = Field(
        alias="descricao",
        title="Descrição",
        min_length=1,
        max_length=1000,
        description="Características que ajudam a identificar o objeto.",
        schema_extra={"examples": ["Garrafa azul com tampa preta"]},
    )
    found_location: str = Field(
        alias="local_encontrado",
        title="Local onde foi encontrado",
        min_length=1,
        max_length=200,
        description="Local do campus onde o objeto foi encontrado.",
        schema_extra={"examples": ["Biblioteca"]},
    )
    found_at: NaiveDatetime = Field(
        alias="encontrado_em",
        title="Data e hora em que foi encontrado",
        description="Data e hora em que o objeto foi encontrado, no horário de São Paulo, sem indicação de fuso.",
        schema_extra={"examples": ["2026-10-25T10:30:00"]},
    )


class Item(ItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class ItemPublic(ItemBase):
    model_config = ConfigDict(title="Item")

    id: int = Field(description="Identificador do item, gerado pelo banco.")
