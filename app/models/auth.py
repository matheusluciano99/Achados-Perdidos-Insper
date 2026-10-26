from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, NaiveDatetime
from sqlmodel import Field, SQLModel

from app.models.user import EmailInsper


class SolicitacaoCodigo(SQLModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, title="Solicitação de código")

    email: EmailInsper = Field(max_length=254, schema_extra={"examples": ["maria@al.insper.edu.br"]})


class ConfirmacaoCodigo(SolicitacaoCodigo):
    model_config = ConfigDict(title="Confirmação do código")

    codigo: str = Field(schema_extra={"pattern": r"^[0-9]{6}$"}, description="Código de seis dígitos recebido por e-mail.")
    nome: str | None = Field(default=None, min_length=1, max_length=100, description="Obrigatório no primeiro acesso.")


class TokenAcesso(SQLModel):
    token_acesso: str
    tipo_token: Literal["bearer"] = "bearer"
    expira_em: datetime


class CodigoLogin(SQLModel, table=True):
    __tablename__ = "codigo_login"

    email: str = Field(primary_key=True, max_length=254)
    codigo_hash: str = Field(max_length=64)
    enviado_em: NaiveDatetime
    expira_em: NaiveDatetime
    tentativas: int = Field(default=0)
