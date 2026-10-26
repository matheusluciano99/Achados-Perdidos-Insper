from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlmodel import Field, SQLModel


class FotoItem(SQLModel, table=True):
    __tablename__ = "foto_item"

    id_item: int = Field(primary_key=True, foreign_key="item.id", ondelete="CASCADE")
    conteudo: bytes = Field(sa_type=MEDIUMBLOB)
